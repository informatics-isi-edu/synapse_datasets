import copy
import pickle

import pandas as pd
import numpy as np

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
        'PrcDsy20170613A': 'conditioned',
        'PrcDsy20170615A': 'unconditioned',
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
            i['Type'] = protocol_types[i['Protocol']]

        try:
            i['Aligned'] = False
            i['Provenence'] = { 'GITHash': githash , 'CatlogVersion': ermrest_snapshot}
            i['Alignment'] = ImageGrossAlignment.from_image_id(ermrest_catalog, i['BeforeImageID'])
            p = pd.DataFrame([i[pt] for pt in ['AlignP0', 'AlignP1', 'AlignP2']])
            p =  p.multiply(pd.DataFrame([{'z': 0.4, 'y': 0.26, 'x': 0.26}]*3))
            i['AlignmentPts'] = pd.DataFrame(transform_points(i['Alignment'].M, p.loc[:,['x','y','z']]),
                                                 columns=['x', 'y', 'z'])
            i['Aligned'] = True
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
    if group =='Aligned':
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
            s['UnpairedBefore'][r] = p

            p = pd.DataFrame(unpaired2[:, 0:5], columns=['z', 'y', 'x', 'core', 'hollow'])
            s['UnpairedAfter'] = s.get('UnpairedAfter', dict())
            s['UnpairedAfter'][r] = p

            p = pd.DataFrame(paired1[:, 0:5], columns=['z', 'y', 'x', 'core', 'hollow'])
            s['PairedBefore'] = s.get('PairedBefore', dict())
            s['PairedBefore'][r] = p

            p = pd.DataFrame(paired2[:, 0:5], columns=['z', 'y', 'x', 'core', 'hollow'])
            s['PairedAfter'] = s.get('PairedAfter', dict())
            s['PairedAfter'][r] = p

            # Fill in other useful values into the pandas so you can use them without having the
            # study handy
            for ptype in ['PairedBefore', 'PairedAfter', 'UnpairedBefore', 'UnpairedAfter']:
                p = s[ptype][r]
                p.DataType = ptype
                p.Study = s['Study']
                p.Radius = r
                p.Type = s['Type']

            # Now compute the aligned images, if you have the tranformation matrix available.
            if s['Aligned']:
                image_obj = s['Alignment']
                for ptype in ['PairedBefore', 'PairedAfter', 'UnpairedBefore', 'UnpairedAfter']:
                    p = pd.DataFrame(transform_points(image_obj.M, s[ptype][r].loc[:, ['x', 'y', 'z']]),
                                     columns=['x', 'y', 'z'])
                    p['core'] = s[ptype][r]['core']
                    p.DataType = 'Aligned' + ptype
                    p.Study = s[ptype][r].Study
                    p.Radius = r

                    s[p.DataType] = s.get(p.DataType, dict())
                    s[p.DataType][r] = p


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

