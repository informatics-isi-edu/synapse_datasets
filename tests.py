%load_ext autoreload
%autoreload 2

import synapse_plot_utils as sp
import pandas as pd
import numpy as np
from  math import floor, ceil

from sklearn.datasets import make_blobs
import hdbscan


dumpfile = 'pairs-dump.pkl'
studyset = sp.restore_studies(dumpfile)
studylist = studyset['Studies']
synapses, syn_max, syn_min = sp.aggregate_studies(studylist)

clusterer = hdbscan.HDBSCAN()
clusterer.fit(synapses['learner']['UnpairedBefore'][['x','y','z']].values)


testlist

counts = sp.bin_synapses(studylist, 4)

# Now collapse in one dimension:
counts2d = { k: counts[k].sum('y')  for k in counts }

# Calculate denstity by normalizing by the total number of synapses in each bin.
density = (counts2d['learner']/counts2d['learner']['AllCounts']).fillna(0)


# Now compute the center of mass
plane_mass = density.sum('x')
centermass_0 = (plane_mass.coords['z'] * plane_mass).sum() / plane_mass.sum()

plane_mass = density.sum('z')
centermass_1 = (plane_mass.coords['x'] * plane_mass).sum() / plane_mass.sum()

centermass = { k : (float(centermass_0[k]), float(centermass_1[k])) for k in centermass_0.data_vars}


def construct_test_pair(study,type, datatype):
    d = { 4:
            {'Study': study,
             'DataType': datatype,
             'Type' : type,
             'Data' : pd.DataFrame(
                 {'x': np.arange(.1, 1.1, .1),
                  'y': np.arange(.1, 1.1, .1),
                  'z': np.arange(.1, 1.1, .1)
                  }
             )
         }
    }
    return d

def construct_test_pair0(study,type, datatype):
    d = { 4:
            {'Study': study,
             'DataType': datatype,
             'Type' : type,
             'Data' : pd.DataFrame(
                 {'x': [1,1,1,4,4,4,1,1,1,4,4,4],
                  'z': [1,4,5,1,4,5,1,4,5,1,4,5],
                  'y': [1,1,1,1,1,1,4,4,4,4,4,4]
                  }
             )
         }
    }
    return d

def construct_test_study(studyname, studytype):
    t = {
        'Study': studyname,
        'Subject': 'Subject1',
        'Type': studytype,
        'StudyID': 'SSet1',
        'AlignedUnpairedBefore' : construct_test_pair0(studyname, studytype, 'AlignedUnpairedBefore'),
        'AlignedUnpairedAfter': construct_test_pair0(studyname, studytype, 'AlignedUnpairedAfter'),
        'AlignedPairedBefore': construct_test_pair0(studyname, studytype, 'AlignedPairedBefore'),
        'AlignedPairedAfter': construct_test_pair0(studyname, studytype, 'AlignedPairedAfter')
    }
    return t

l = [ construct_test_study('foo','learner'), construct_test_study('bar','learner') ]
a = sp.aggregate_studies(l)
c = sp.bin_synapses(l,4)
d = sp.synapse_density(c)
d = sp.synapse_density3d(c)


