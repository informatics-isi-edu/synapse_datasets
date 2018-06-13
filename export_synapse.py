import synapse_utils
import synapse_plot_utils as sp
from synapse_plot_config import plot_synapses, trace_color, position_layout, step_buttons, studytypes

from deriva.core import ErmrestCatalog, get_credential

protocol_types = {
    'PrcDsy20160101A': 'aversion',
    'PrcDsy20170613A': 'conditioned',
    'PrcDsy20170615A': 'unconditioned',
    'PrcDsy20170613B': 'fullcycle-control',
    'PrcDsy20171030A': 'groundtruth-control',
    'PrcDsy20171030B': 'interval-groundtruth-control'
}

bag_metadata = {
    'External-Description': 'Synapse Pair Datasets',
}


def studyset_to_bag(studyset, dest, protocol_types, bag_metadata=None, publish=False):
    """
    Export all of the synapse data for every study in the study list.
    Also output a CVS file that contains an index of all of the data.

    The data indes is: StudyID, SubjectID, Study Type, FileNames for Before and After synapses.

    """

    bag_metadata = bag_metadata if bag_metadata else {}

    study_list = studyset['Studies']

    current_dir = os.getcwd()
    try:
        os.chdir(dest)

        # Create an output directory for synapse files.
        os.makedirs('synapse-studies', mode=0o777, exist_ok=True)
        os.chdir('synapse-studies')

        dumpdir = os.getcwd()

        os.makedirs('synapse-data', mode=0o777, exist_ok=True)

        for study in study_list:
            # radius of four....
            for d in ['UnpairedBefore', 'UnpairedAfter', 'PairedBefore']:
                fn = 'synapse-data/' + study['Study'] + '-' + study['Type'] + '-' + d + '.csv'
                study[d][4]['Data'].to_csv(fn)

        # Now write out the CSV file will the list of studies...
        with open('studies.csv', 'w', newline='') as csvfile:
            synapsewriter = csv.writer(csvfile)

            # Write out header....
            synapsewriter.writerow(['Study', 'Subject', 'Type'])
            for study in study_list:
                url1 = study['BeforeURL']
                url2 = study['AfterURL']

                filename1 = filename2 = ''
                if url1:
                    filename1 = (os.path.basename(url1.split(':')[0]))
                if url2:
                    filename2 = (os.path.basename(url2.split(':')[0]))

                synapsewriter.writerow([study['Study'], study['Subject'], study['Type']])

        bdb.make_bag(dumpdir, metadata=bag_metadata)
        archivefile = bdb.archive_bag(dumpdir, 'zip')

        if publish:
            bagstore = HatracStore('https', 'synapse-dev.isrd.isi.edu', credentials=credential)
            hatrac_path = '/hatrac/Data/synapse-{0}'.format(bag_metadata['ERMRest-Snapshot'])
            return bagstore.put_obj(hatrac_path, archivefile)
    finally:
        os.chdir(current_dir)
    return archivefile


def synapses_to_bag(study_list, dest, protocol_types, bag_metadata=None, publish=False):
    """
    Export all of the synapse data for every study in the study list.
    Also output a CVS file that contains an index of all of the data.

    The data indes is: StudyID, SubjectID, Study Type, FileNames for Before and After synapses.

    """

    bag_metadata = bag_metadata if bag_metadata else {}

    credential = get_credential("synapse.isrd.isi.edu")
    objectstore = HatracStore('https', 'synapse.isrd.isi.edu', credentials=credential)

    current_dir = os.getcwd()
    try:
        os.chdir(dest)

        # Create an output directory for synapse files.
        os.makedirs('synapse-studies', mode=0o777, exist_ok=True)
        os.chdir('synapse-studies')
        dumpdir = os.getcwd()

        for study in study_list:
            copy_synapse_files(objectstore, study)

        # Now write out the CSV file will the list of studies...
        with open('studies.csv', 'w', newline='') as csvfile:
            synapsewriter = csv.writer(csvfile)

            # Write out header....
            synapsewriter.writerow(['Study', 'Subject', 'Type', 'Learner', 'Before', 'After'])
            for study in study_list:
                study_type = protocol_types[study['Protocol']]
                url1 = study['BeforeURL']
                url2 = study['AfterURL']

                filename1 = filename2 = ''
                if url1:
                    filename1 = (os.path.basename(url1.split(':')[0]))
                if url2:
                    filename2 = (os.path.basename(url2.split(':')[0]))

                synapsewriter.writerow([study['Study'], study['Subject'], study_type, study['Learner'],
                                        filename1, filename2])

        bdb.make_bag(dumpdir, metadata=bag_metadata)
        archivefile = bdb.archive_bag(dumpdir, 'zip')

        if publish:
            bagstore = HatracStore('https', 'synapse-dev.isrd.isi.edu', credentials=credential)
            hatrac_path = '/hatrac/Data/synapse-{0}'.format(bag_metadata['ERMRest-Snapshot'])
            return bagstore.put_obj(hatrac_path, archivefile)
    finally:
        os.chdir(current_dir)
    return archivefile


studyid = '10DJ@2PS-H8ZM-3F2G'
studyset = synapse_utils.fetch_studies(studyid)
studylist = studyset['Studies']
study_types = studytypes(studylist)

# Get the entity list of studies.....
#study_entities = synapse_utils.get_synapse_studies(studyid)
#print('Identified %d studies' % len(study_entities))

# This is a hack until we get get right version support in PathBuilder
ermrest_version = vc.current_catalog_version(
#    ErmrestCatalog('https', 'synapse.isrd.isi.edu', 1,
#                   get_credential('synapse.isrd.isi.edu')))

# Set some additional bag metadata
#bag_metadata['ERMRest-Query'] = vc.versioned_path(study_entities.uri, ermrest_version)
#bag_metadata['ERMRest-Snapshot'] = ermrest_version

# now dump out the bag and publish to hatrac
#archive = synapse_utils.synapses_to_bag(study_entities, destdir, protocol_types, bag_metadata)
archive = synapse_utils.studyset_to_bag(studyset, destdir, protocol_types, bag_metadata)

print('Dumped studies')

#syn_pair_radii = (4, 300.0,) # maximum search radii
syn_pair_radii = [4]
syn_dx_core_ratio = None  # turn off 4D nearest-neighbor
syn_core_max_ratio = None # turn off intensity ratio threshold
synapse_utils.dump_studies(synapse_utils.compute_studies('TYR',syn_pair_radii), 'study-TYR.pkl')
