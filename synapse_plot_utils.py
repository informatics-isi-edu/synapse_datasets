import pandas as pd
import xarray as xr
from math import floor, ceil

synapseserver = 'synapse-dev.isrd.isi.edu'

# Helpful list....
pair_types = ['Before', 'After',
              'PairedBefore', 'PairedAfter',
              'UnpairedBefore', 'UnpairedAfter',
              'AlignedBefore', 'AlignedAfter'
              'AlignedPairedBefore', 'AlignedPairedAfter',
              'AlignedUnpairedBefore', 'AlignedUnpairedAfter']

def aggregate_studies(studylist):
    """
    Go through the list of studies and agregate all of the synapses into a single list for each study type.
    :param studylist:
    :return: A dictionary for all, learners, nonlearners, and each control type, that aggregates
            the synapses by the all, before and after and paired.  We only use the before paired.
    """
    r = min(studylist[0]['AlignedUnpairedBefore'])

    study_types = {s['Type'] for s in studylist}
    # Add a pseudo type which is for all studies.
    study_types.add('all')

    # Initialize resulting synapse dictionary so we have an entry for each study type.
    synapses = {t: {'All': pd.DataFrame(columns=['x', 'y', 'z']),
                    'Before': pd.DataFrame(columns=['x', 'y', 'z']),
                    'After': pd.DataFrame(columns=['x', 'y', 'z']),
                    'PairedBefore': pd.DataFrame(columns=['x', 'y', 'z']),
                    'PairedAfter': pd.DataFrame(columns=['x', 'y', 'z']),
                    'UnpairedBefore': pd.DataFrame(columns=['x', 'y', 'z']),
                    'UnpairedAfter': pd.DataFrame(columns=['x', 'y', 'z'])}
                for t in study_types
                }
    max_x, max_y, max_z = -float('inf'), -float('inf'), -float('inf')
    min_x, min_y, min_z = float('inf'), float('inf'), float('inf')
    for s in studylist:
        for i in ['UnpairedBefore', 'UnpairedAfter', 'PairedBefore', 'PairedAfter']:
            pts = s['Aligned' + i][r]['Data']
            # Accumulate points for all studies
            synapses['all'][i] = synapses['all'][i].append(pts, ignore_index=True, sort=False)
            synapses['all']['All'] = synapses['all']['All'].append(pts, ignore_index=True,sort=False)
            # Accumulate for studys by type...
            synapses[s['Type']][i] = synapses[s['Type']][i].append(pts, ignore_index=True, sort=False)
            synapses[s['Type']]['All'] = synapses[s['Type']]['All'].append(pts, ignore_index=True, sort=False)
            if 'Before' in i:
                synapses[s['Type']]['Before'] = synapses[s['Type']]['Before'].append(pts, ignore_index=True, sort=False)
            else:
                synapses[s['Type']]['After'] = synapses[s['Type']]['After'].append(pts, ignore_index=True, sort=False)
            max_x, max_y, max_z = max(max_x, pts.max()['x']), max(max_y, pts.max()['y']), max(max_z, pts.max()['z'])
            min_x, min_y, min_z = min(min_x, pts.min()['x']), min(min_y, pts.min()['y']), min(min_z, pts.min()['z'])
    return synapses, (max_x, max_y, max_z), (min_x, min_y, min_z)


def bin_synapses(studylist, nbins=10):
    """
    Compute the density of a set of synapses. Input is a dictionary with key: All, PairedBefore, PairedAfter, ....
    :param studylist:
    :param nbins
    :return:
    """

    binned_synapses = {}
    agg_synapses, smax, smin = aggregate_studies(studylist)

    # Go through the set of synapse study types (learner, nonlearner, ....)
    for type, synapses in agg_synapses.items():
        # Find the smallest range in x, y and z so we can figure out the bin sizes by dividing by the number of bins
        binsize = min([smax[i] - smin[i] for i in range(3)]) / nbins
        ds = xr.Dataset()
        ds.attrs['binsize'] = binsize
        ds.attrs['min'] = smin
        ds.attrs['max'] = smax
        ds.attrs['type'] = 'count'
        for k, v in enumerate(synapses):
            bins = {}
            for idx, c in enumerate(['x', 'y', 'z']):
                # The number of bins will be determined by the range on the access and the binsize
                nbins = int(ceil((smax[idx] - smin[idx]) / binsize))

                # Now create an index that maps the coordinates into the bins
                bins[c] = pd.cut(synapses[v][c],
                                 [smin[idx] + i * binsize for i in range(nbins + 1)],
                                 labels=[smin[idx] + i * binsize for i in range(nbins)],
                                 include_lowest=True)

            # Compute the number of synapses in the binned plane by grouping in the axis and counting them.
            counts = synapses[v].groupby([bins['x'], bins['y'], bins['z']]).size()

            # Convert the panda to a dataset, unpack the multi-index to get X,Y dimensions, and then finally,
            # fill in the NaN that result from empty bins with 0.
            ds[v] = xr.DataArray(counts).unstack('dim_0').fillna(0)
        binned_synapses[type] = ds
    return binned_synapses


def synapse_density(binned_synapses, axis='y', mode='density', threshold=0):
    """
    Compute the density of a set of synapses. Input is a dictionary with key: All, PairedBefore, PairedAfter, ....
    :param studylist:
    :param nbins:
    :param axis:
    :return:
    """

    # Set the plane that we want to calculate density over.
    if axis == 'y':
        c0, c1 = 'z', 'x'
    elif axis == 'x':
        c0, c1 = 'y', 'z'
    else:
        c0, c1 = 'x', 'y'

    density = {}
    # Go through the study types: learner, nonlearner, ...
    for t, counts in binned_synapses.items():
        # Now collapse in one dimension:
        counts2d = counts.sum(axis).transpose()
        if mode == 'bin':
            # Calculate denstity by normalizing by the total number of synapses in each bin.
           density[t] = (counts2d / counts2d['All']).fillna(0)
        elif mode == 'total':
            # Normalize by the total number of synapses .
            density[t] = (counts2d / counts2d['All'].sum()).fillna(0)
        else: # mode = density:
            # Use the number of synapes in each type
            density[t] = (counts2d / counts.sum()).fillna(0)

        dmax = density[t].max()*threshold
        density[t] = density[t].where(density[t] > dmax, 0)

        density[t].attrs = counts.attrs
        density[t].attrs['type'] = 'density'


        # Now compute the center of mass
        plane_mass = density[t].sum(c0)
        centermass_0 = (plane_mass.coords[c1] * plane_mass).sum() / plane_mass.sum()

        plane_mass = density[t].sum(c1)
        centermass_1 = (plane_mass.coords[c0] * plane_mass).sum() / plane_mass.sum()

        for k in centermass_0.data_vars:
            density[t][k].attrs['center_of_mass'] = (float(centermass_0[k]), float(centermass_1[k]))
            print('2d COM:', t, k, density[t][k].attrs['center_of_mass'])
    return density


def synapse_density3d(binned_synapses, threshold=0):
    """
    Compute the density of a set of synapses. Input is a dictionary with key: All, PairedBefore, PairedAfter, ....
    :param studylist:
    :param nbins:
    :param axis:
    :return:
    """

    density = {}
    # Go through the study types: learner, nonlearner, ...
    for t, counts in binned_synapses.items():
        # Use the number of synapes in each type
        density[t] = (counts / counts.sum()).fillna(0)

        dmax = density[t].max() * threshold
        density[t] = density[t].where(density[t] > dmax, 0)

        density[t].attrs = counts.attrs
        density[t].attrs['type'] = 'density'

        # Now compute the center of mass
        plane_mass = density[t].sum(['y']).sum(['z'])
        centermass_x = (plane_mass.coords['x'] * plane_mass).sum() / plane_mass.sum()

        plane_mass = density[t].sum(['x']).sum(['z'])
        centermass_y = (plane_mass.coords['y'] * plane_mass).sum() / plane_mass.sum()

        plane_mass = density[t].sum(['x']).sum(['y'])
        centermass_z = (plane_mass.coords['z'] * plane_mass).sum() / plane_mass.sum()

        for k in centermass_x.data_vars:
            density[t][k].attrs['center_of_mass'] = \
                (float(centermass_x[k]), float(centermass_y[k]), float(centermass_z[k]))
    return density


