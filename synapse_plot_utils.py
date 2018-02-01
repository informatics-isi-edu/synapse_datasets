import copy
import pickle

import pandas as pd
import numpy as np
import xarray as xr
from math import floor, ceil

import os
import subprocess

import synapse_utils
from synspy.analyze.pair import SynapticPairStudy, ImageGrossAlignment, transform_points

from deriva.core import HatracStore, ErmrestCatalog, get_credential

def get_studies() :

    credential = get_credential("synapse.isrd.isi.edu")
    ermrest_catalog = ErmrestCatalog('https', 'synapse.isrd.isi.edu', 1, credential)
    hatrac_store = HatracStore('https', 'synapse.isrd.isi.edu', credentials=credential)

    githash = git_version()
    ermrest_snapshot = catalog_snapshot()

# Get the current list of studies from the server.
    study_entities = synapse_utils.get_synapse_studies()

    print('Identified %d studies' % len(study_entities))

    protocol_types = {
        'PrcDsy20160101A': 'aversion',
        'PrcDsy20170613A': 'conditioned-control',
        'PrcDsy20170615A': 'unconditioned-control',
        'PrcDsy20170613B': 'fullcycle-control',
        'PrcDsy20171030A': 'groundtruth-control',
        'PrcDsy20171030B': 'interval-groundtruth-control'
    }

    # Compute the alignment for each study, and fill in some useful values.
    for i in study_entities:
        i['Paired'] = False
        if protocol_types[i['Protocol']] == 'aversion':
            if i['Learner'] == True:
                i['Type'] = 'learner'
            else:
                i['Type'] = 'nonlearner'
        else:
#            i['Type'] = protocol_types[i['Protocol']]
            i['Type'] = 'control'

        try:
            i['Aligned'] = False
            i['Provenence'] = { 'GITHash': githash , 'CatlogVersion': ermrest_snapshot}
            i['Alignment'] = ImageGrossAlignment.from_image_id(ermrest_catalog, i['BeforeImageID'])
            p = pd.DataFrame([i[pt] for pt in ['AlignP0', 'AlignP1', 'AlignP2']])
            p =  p.multiply(pd.DataFrame([{'z': 0.4, 'y': 0.26, 'x': 0.26}]*3))
            i['StudyAlignmentPts'] = pd.DataFrame(transform_points(i['Alignment'].M, p.loc[:,['x','y','z']]),
                                                 columns=['x', 'y', 'z'])
            i['Aligned'] = True
            i['AlignmentPts'] = dict()
        except ValueError:  # Alignments missing....
            continue
        except NotImplementedError:
            print('Alignment Code Failed for study: {0}'.format(i['Study']))
            continue

    return list(study_entities)


# Helpful list....
pair_types = ['PairedBefore', 'PairedAfter',
              'UnpairedBefore', 'UnpairedAfter',
              'AlignedPairedBefore', 'AlignedPairedAfter',
              'AlignedUnpairedBefore', 'AlignedUnpairedAfter']


def group_studies(studies, group='Type'):
    '''
    Return a dictionary whose key it a type, subject, or alignment and whose value is a list of studies'''
    if group == 'Type':
        key = 'Type'
    if group == 'Subject':
        key = 'Subject'
    if group == 'Aligned':
        key = 'Aligned'
    g = dict()
    for i in studies:
        g[i[key]] = g.get(i[key],[]) + [i]
    return g


def compute_pairs(studylist, radii, ratio=None, maxratio=None):
    print('Finding pairs for {0} studies'.format(len(studylist)))

    credential = get_credential("synapse.isrd.isi.edu")
    ermrest_catalog = ErmrestCatalog('https', 'synapse.isrd.isi.edu', 1, credential)
    hatrac_store = HatracStore('https', 'synapse.isrd.isi.edu', credentials=credential)

    for s in studylist:
        syn_study_id = s['Study']
        s['Paired'] = True

        print('Processing study {0}'.format(syn_study_id))
        study = SynapticPairStudy.from_study_id(ermrest_catalog, syn_study_id)
        study.retrieve_data(hatrac_store)

        # Compute the actual pairs for the given distances
        s1_to_s2, s2_to_s1 = study.syn_pairing_maps(radii, ratio, maxratio)

        # get results for different radii, store them in a dictonary of pandas
        for i, r in enumerate(radii):

            unpaired1 = study.get_unpaired(s1_to_s2[i, :], study.s1)
            unpaired2 = study.get_unpaired(s2_to_s1[i, :], study.s2)
            paired1, paired2 = study.get_pairs(s1_to_s2[i, :], study.s1, study.s2)

            p = pd.DataFrame(unpaired1[:, 0:5], columns=['z', 'y', 'x', 'core', 'hollow'])
            s['UnpairedBefore'] = s.get('UnpairedBefore', dict())
            s['UnpairedBefore'][r] = {'Data': p}

            p = pd.DataFrame(unpaired2[:, 0:5], columns=['z', 'y', 'x', 'core', 'hollow'])
            s['UnpairedAfter'] = s.get('UnpairedAfter', dict())
            s['UnpairedAfter'][r] = {'Data': p}

            p = pd.DataFrame(paired1[:, 0:5], columns=['z', 'y', 'x', 'core', 'hollow'])
            s['PairedBefore'] = s.get('PairedBefore', dict())
            s['PairedBefore'][r] = {'Data': p}

            p = pd.DataFrame(paired2[:, 0:5], columns=['z', 'y', 'x', 'core', 'hollow'])
            s['PairedAfter'] = s.get('PairedAfter', dict())
            s['PairedAfter'][r] = {'Data': p}

            # Fill in other useful values so you can use them without having the study handy
            for ptype in ['PairedBefore', 'PairedAfter', 'UnpairedBefore', 'UnpairedAfter']:
                p = s[ptype][r]
                p['DataType'] = ptype
                p['Study'] = s['Study']
                p['Radius'] = r
                p['Type'] = s['Type']

            # now compute the centroids and store as pandas.
            for ptype in ['PairedBefore', 'PairedAfter', 'UnpairedBefore', 'UnpairedAfter']:
                p = s[ptype][r]['Data']
                centroid = tuple([p['x'].mean(), p['y'].mean(), p['z'].mean()])
                pc = pd.DataFrame.from_records([centroid], columns=['x', 'y', 'z'])
                cname = ptype + 'Centroid'
                s[cname] = s.get(cname, dict())
                s[cname][r] = {'Data': pc}
                p = s[cname][r]
                p['DataType'] = cname
                p['Study'] = s['Study']
                p['Radius'] = r
                p['Type'] = s['Type']

            # Now compute the aligned images, if you have the tranformation matrix available.
            if s['Aligned']:
                image_obj = s['Alignment']
                s['AlignmentPts'][r] = {'Data': s['StudyAlignmentPts']}
                for ptype in ['PairedBefore', 'PairedAfter', 'UnpairedBefore', 'UnpairedAfter']:
                    p = pd.DataFrame(transform_points(image_obj.M, s[ptype][r]['Data'].loc[:, ['x', 'y', 'z']]),
                                     columns=['x', 'y', 'z'])
                    p['core'] = s[ptype][r]['Data']['core']

                    # Now do th aligned ....
                    datatype = 'Aligned' + ptype
                    s[datatype] = s.get(datatype, dict())
                    s[datatype][r] = {'Data': p}
                    s[datatype][r]['DataType'] = datatype
                    s[datatype][r]['Study'] = s['Study']
                    s[datatype][r]['Radius'] = r
                    s[datatype][r]['Type'] = s['Type']

                    # now compute the aligned centroids and store as pandas.
                    centroid = tuple([p['x'].mean(), p['y'].mean(), p['z'].mean()])
                    pc = pd.DataFrame.from_records([centroid], columns=['x', 'y', 'z'])
                    cname = datatype + 'Centroid'
                    s[cname] = s.get(cname, dict())
                    s[cname][r] = {'Data': pc}
                    s[cname]['DataType'] = cname
                    s[cname]['Study'] = s['Study']
                    s[cname]['Radius'] = r
                    s[cname]['Type'] = s['Type']


def aggregate_pairs(studylist, tracelist):
    r = min(studylist[0][tracelist[0]])

    synapses = {}
    synapses['all'] = {'all': pd.DataFrame(columns=['x', 'y', 'z']),
                       'before': pd.DataFrame(columns=['x', 'y', 'z']),
                       'after': pd.DataFrame(columns=['x', 'y', 'z'])}

    synapses['learner'] = {'all': pd.DataFrame(columns=['x', 'y', 'z']),
                           'before': pd.DataFrame(columns=['x', 'y', 'z']),
                           'after': pd.DataFrame(columns=['x', 'y', 'z'])}

    synapses['nonlearner'] = {'all': pd.DataFrame(columns=['x', 'y', 'z']),
                              'before': pd.DataFrame(columns=['x', 'y', 'z']),
                              'after': pd.DataFrame(columns=['x', 'y', 'z'])}

    synapses['control'] = {'all': pd.DataFrame(columns=['x', 'y', 'z']),
                           'before': pd.DataFrame(columns=['x', 'y', 'z']),
                           'after': pd.DataFrame(columns=['x', 'y', 'z'])}

    for s in studylist:
        before = s['AlignedUnpairedBefore'][r]['Data']
        after = s['AlignedUnpairedAfter'][r]['Data']

        synapses['all']['before'] = synapses['all']['before'].append(before, ignore_index=True)
        synapses['all']['after'] = synapses['all']['after'].append(after, ignore_index=True)
        if s['Type'] == 'learner':
            synapses['learner']['before'] = synapses['learner']['before'].append(before, ignore_index=True)
            synapses['learner']['after'] = synapses['learner']['after'].append(after, ignore_index=True)
        elif s['Type'] == 'nonlearner':
            synapses['nonlearner']['before'] = synapses['nonlearner']['before'].append(before, ignore_index=True)
            synapses['nonlearner']['after'] = synapses['nonlearner']['after'].append(after, ignore_index=True)
        else:
            synapses['control']['before'] = synapses['control']['before'].append(before, ignore_index=True)
            synapses['control']['after'] = synapses['control']['after'].append(after, ignore_index=True)
    return synapses


def synapse_density(synapses, nbins=10, plane=None):

    # Set the plane that we want to calculate density over.
    if not plane:
        plane = ['x', 'z']

    # Find the smallest range in x, y and z so we can figure out the bin sizes by dividing by the number of bins
    binsize = (synapses[['x', 'y', 'z']].max() - synapses[['x', 'y', 'z']].min()).min() / nbins

    bins = {}
    for c in ['x', 'y', 'z']:
        # The number of bins will be determined by the range on the access and the binsize
        nbins = ceil((synapses[c].max() - synapses[c].min()) / binsize)

        # Now create an index that maps the coordinates into the bins
        bins[c] = pd.cut(synapses[c],
                      [synapses[c].min() + i * binsize for i in range(nbins + 1)],
                      labels=[synapses[c].min() + i * binsize for i in range(nbins)],
                      include_lowest=True)

    # Compute the number of synapses in the binned plane by grouping in the axis and counting them.
#    density = synapses['x'].groupby([bins[plane[0]], bins[plane[1]]]).count().reset_index(name='count')
#    density['density'] = density['count']/len(synapses)

    counts = synapses.groupby([bins[plane[0]], bins[plane[1]]]).size()

    # Convert the panda to a dataset, unpack the multi-index to get X,Y dimensions, and then finally,
    # fill in the NaN that result from empty bins with 0.
    ds = xr.Dataset({'counts': counts}).unstack('dim_0').fillna(0)

    # Now add another array for density.
    ds['density'] = ds['counts'] / ds['counts'].sum()

    return ds


def dump_studies(slist, fname):
    with open(fname, 'wb') as fo:
        pickle.dump(slist, fo)
        print('dumped {0} studies to {1}'.format(len(slist), fname))


def restore_studies(fname):
    with open(fname, 'rb') as fo:
        slist = pickle.load(fo)

    print('Restored {0} studies'.format(len(slist)))
    return slist


# Return the git revision as a string
def git_version():
    def _minimal_ext_cmd(cmd):
        # construct minimal environment
        env = {}
        for k in ['SYSTEMROOT', 'PATH']:
            v = os.environ.get(k)
            if v is not None:
                env[k] = v
        # LANGUAGE is used on win32
        env['LANGUAGE'] = 'C'
        env['LANG'] = 'C'
        env['LC_ALL'] = 'C'
        out = subprocess.Popen(cmd, stdout = subprocess.PIPE, env=env).communicate()[0]
        return out

    try:
        out = _minimal_ext_cmd(['git', 'rev-parse', 'HEAD'])
        GIT_REVISION = out.strip().decode('ascii')
    except OSError:
        GIT_REVISION = "Unknown"

    return GIT_REVISION


def catalog_snapshot():
        credential = get_credential("synapse.isrd.isi.edu")
        catalog = ErmrestCatalog('https', 'synapse.isrd.isi.edu', 1, credential)
        # Get current version of catalog and construct a new URL that fully qualifies catalog with version.
        version = catalog.get('/').json()['snaptime']
        return version

