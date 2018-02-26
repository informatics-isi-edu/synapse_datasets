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

from deriva.core import HatracStore, ErmrestCatalog, get_credential, DerivaPathError


def get_studies(studyid):

    credential = get_credential("synapse.isrd.isi.edu")
    ermrest_catalog = ErmrestCatalog('https', 'synapse.isrd.isi.edu', 1, credential)
    hatrac_store = HatracStore('https', 'synapse.isrd.isi.edu', credentials=credential)

    githash = git_version()
    ermrest_snapshot = catalog_snapshot()

# Get the current list of studies from the server.
    study_entities = synapse_utils.get_synapse_studies(studyid)

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
            if i['Learner'] is True:
                i['Type'] = 'learner'
            else:
                i['Type'] = 'nonlearner'
        else:
            i['Type'] = protocol_types[i['Protocol']]

        try:
            i['Aligned'] = False
            i['Provenence'] = {'GITHash': githash, 'CatlogVersion': ermrest_snapshot}
            i['StudyID'] = studyid
            i['Alignment'] = ImageGrossAlignment.from_image_id(ermrest_catalog, i['BeforeImageID'])
            p = pd.DataFrame([i[pt] for pt in ['AlignP0', 'AlignP1', 'AlignP2']])
            p = p.multiply(pd.DataFrame([{'z': 0.4, 'y': 0.26, 'x': 0.26}]*3))
            i['StudyAlignmentPts'] = pd.DataFrame(transform_points(i['Alignment'].M, p.loc[:,['x','y','z']]),
                                                 columns=['x', 'y', 'z'])
            i['Aligned'] = True
            i['AlignmentPts'] = dict()
        except ValueError:  # Alignments missing....
            continue
        except NotImplementedError:
            print('Alignment Code Failed for study: {0}'.format(i['Study']))
            continue

    return { 'StudyID': studyid,
             'Studies': list(study_entities),
             'Provenence': {'GITHash': githash, 'CatlogVersion': ermrest_snapshot}
             }

# Helpful list....
pair_types = ['PairedBefore', 'PairedAfter',
              'UnpairedBefore', 'UnpairedAfter',
              'AlignedPairedBefore', 'AlignedPairedAfter',
              'AlignedUnpairedBefore', 'AlignedUnpairedAfter']


def group_studies(studies, group='Type'):
    """
    Return a dictionary whose key it a type, subject, or alignment and whose value is a list of studies
    """
    if group == 'Type':
        key = 'Type'
    if group == 'Subject':
        key = 'Subject'
    if group == 'Aligned':
        key = 'Aligned'
    g = dict()
    for i in studies:
        g[i[key]] = g.get(i[key], []) + [i]
    return g


def compute_pairs(studylist, radii, ratio=None, maxratio=None):
    print('Finding pairs for {0} studies'.format(len(studylist)))

    credential = get_credential("synapse.isrd.isi.edu")
    ermrest_catalog = ErmrestCatalog('https', 'synapse.isrd.isi.edu', 1, credential)
    hatrac_store = HatracStore('https', 'synapse.isrd.isi.edu', credentials=credential)

    pairlist = []
    for s in studylist:
        syn_study_id = s['Study']
        s['Paired'] = True

        print('Processing study {0}'.format(syn_study_id))
        study = SynapticPairStudy.from_study_id(ermrest_catalog, syn_study_id)
        try:
            study.retrieve_data(hatrac_store)
        except DerivaPathError:
            print('Study {0} missing synaptic pair'.format(syn_study_id))
            continue
        pairlist.append(s)

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
                    pc = pd.DataFrame.from_records([centroid], columns=['x', 'y', 'z'])
                    cname = datatype + 'Centroid'
                    s[cname] = s.get(cname, dict())
                    s[cname][r] = {'Data': pc}
                    s[cname]['DataType'] = cname
                    s[cname]['Study'] = s['Study']
                    s[cname]['Radius'] = r
                    s[cname]['Type'] = s['Type']
    return pairlist


def aggregate_studies(studylist):
    """
    Go through the list of studies and agregate all of the synapses into a single list for each study type.
    :param studylist:
    :return: A dictionary for all, learners, nonlearners, and each control type, that aggregates
            the synapses by the all, before and after and paired.  We only use the before paired.
    """
    r = min(studylist[0]['AlignedUnpairedBefore'])

    study_types = {s['Type'] for s in studylist}
    study_types.add('all')

    # Initialize resulting synapse dictionary so we have an entry for each study type.
    synapses = {t: {'All': pd.DataFrame(columns=['x', 'y', 'z']),
                     'PairedBefore': pd.DataFrame(columns=['x', 'y', 'z']),
                     'PairedAfter': pd.DataFrame(columns=['x', 'y', 'z']),
                     'UnpairedBefore': pd.DataFrame(columns=['x', 'y', 'z']),
                     'UnpairedAfter': pd.DataFrame(columns=['x', 'y', 'z'])}
                for t in study_types
                }
    max_x, max_y, max_z = -float('inf'), -float('inf'), -float('inf')
    min_x, min_y, min_z = float('inf'), float('inf'), float('inf')
    for s in studylist:
        for i in ['UnpairedBefore', 'UnpairedAfter', 'PairedBefore']:
            pts = s['Aligned' + i][r]['Data']
            synapses['all'][i] = synapses['all'][i].append(pts, ignore_index=True)
            synapses[s['Type']][i] = synapses[s['Type']][i].append(pts, ignore_index=True)
            synapses[s['Type']]['All'] = synapses[s['Type']]['All'].append(pts, ignore_index=True)
            max_x, max_y, max_z = max(max_x, pts.max()['x']), max(max_y, pts.max()['y']), max(max_z, pts.max()['z'])
            min_x, min_y, min_z = min(min_x, pts.min()['x']), min(min_y, pts.min()['y']), min(min_z, pts.min()['z'])
    return synapses, (max_x, max_y, max_z), (min_x, min_y, min_z)

def bin_synapses(synapses, smax, smin, nbins=10):
    """
    Compute the density of a set of synapses. Input is a dictionary with key: All, PairedBefore, PairedAfter, ....
    :param synapses:
    :param smax: upper right corner of bounding box
    :param smin: lower left corner of bounding box
    :param nbins:
    :param plane:
    :return:
    """

    # Find the smallest range in x, y and z so we can figure out the bin sizes by dividing by the number of bins
    binsize = min([smax[i] - smin[i] for i in range(3)]) / nbins
    ds = xr.Dataset()
    ds.attrs['binsize'] = binsize
    for k,v in enumerate(synapses):
        bins = {}
        for idx, c in enumerate(['x', 'y', 'z']):
            # The number of bins will be determined by the range on the access and the binsize
            nbins = ceil((smax[idx] - smin[idx]) / binsize)
            print(c, nbins)
            # Now create an index that maps the coordinates into the bins
            bins[c] = pd.cut(synapses[v][c],
                             [smin[idx] + i * binsize for i in range(nbins + 1)],
                             labels=[smin[idx] + i * binsize for i in range(nbins)],
                             include_lowest=True)

        # Compute the number of synapses in the binned plane by grouping in the axis and counting them.
        counts = synapses[v].groupby([bins['x'],bins['y'],bins['z']]).size()

        # Convert the panda to a dataset, unpack the multi-index to get X,Y dimensions, and then finally,
        # fill in the NaN that result from empty bins with 0.
        ds[v + 'Counts'] = xr.DataArray(counts).unstack('dim_0').fillna(0)
    return ds

def synapse_density(synapses, smax, smin, nbins=10, plane=None):
    """
    Compute the density of a set of synapses. Input is a dictionary with key: All, PairedBefore, PairedAfter, ....
    :param synapses:
    :param smax: upper right corner of bounding box
    :param smin: lower left corner of bounding box
    :param nbins:
    :param plane:
    :return:
    """

    # Set the plane that we want to calculate density over.
    if not plane:
        plane = ['x', 'z']

    # Find the smallest range in x, y and z so we can figure out the bin sizes by dividing by the number of bins
    binsize = min([smax[i] - smin[i] for i in range(3)]) / nbins
    ds = xr.Dataset()
    ds.attrs['binsize'] = binsize
    for k,v in enumerate(synapses):
        bins = {}
        for idx, c in enumerate(['x', 'y', 'z']):
            # The number of bins will be determined by the range on the access and the binsize
            nbins = ceil((smax[idx] - smin[idx]) / binsize)
            # Now create an index that maps the coordinates into the bins
            bins[c] = pd.cut(synapses[v][c],
                             [smin[idx] + i * binsize for i in range(nbins + 1)],
                             labels=[smin[idx] + i * binsize for i in range(nbins)],
                             include_lowest=True)

        # Compute the number of synapses in the binned plane by grouping in the axis and counting them.
        counts = synapses[v].groupby([bins['x'],bins['y'],bins['z']]).size()

        # Convert the panda to a dataset, unpack the multi-index to get X,Y dimensions, and then finally,
        # fill in the NaN that result from empty bins with 0.
        ds[v + 'Counts'] = xr.DataArray(counts).unstack('dim_0').fillna(0)
    # Now add another array for density.
    #  ds['density'] = ds['counts'] / ds['counts'].sum()

    # Now compute the center of mass and add this as an attribute
    # plane_mass = ds['density'].sum(plane[1])
    # centermass_0 = 0
    #   centermass_0 = centermass_0 + float(i) * float(plane_mass.loc[i])
    #centermass_0 = centermass_0 / float(plane_mass.sum())

    # plane_mass = ds['density'].sum(plane[0])
    # centermass_1 = 0
    # for i in plane_mass.coords[plane[1]]:
    #     centermass_1 = centermass_1 + float(i) * float(plane_mass.loc[i])
    # centermass_1 = centermass_1 / float(plane_mass.sum())

    # ds['density'].attrs['center_of_mass'] = (centermass_0, centermass_1)

    return ds


def dump_studies(sset, fname):
    with open(fname, 'wb') as fo:
        pickle.dump(sset, fo)
        print('dumped {0} studies to {1}'.format(len(sset['Studies']), fname))


def restore_studies(fname):
    with open(fname, 'rb') as fo:
        slist = pickle.load(fo)

    print('Restored {0} studies'.format(len(slist['Studies'])))
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

