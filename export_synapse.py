import synapse_utils
import os

protocol_types = {
    'PrcDsy20160101A': 'aversion',
    'PrcDsy20170613A': 'conditioned',
    'PrcDsy20170615A': 'unconditioned',
    'PrcDsy20170613B': 'fullcycle-control',
    'PrcDsy20171030A': 'groundtruth-control',
    'PrcDsy20171030B': 'interval-groundtruth-control'
}


bag_metadata = {
    'External-Description' : 'Synapse Pair Datasets',
    'EMMRest-Query' : 'This is completely arbitrary'

}


destdir = '/Users/carl/Desktop'


def export_files(study_entities, dest, bag_metadata = None):
    # Dump out the synapses to a local directory

    study_list = []
    for i in study_entities:
        if protocol_types[i['Protocol']] == 'aversion':
            i['Type'] = 'learner' if i['Learner'] is True else 'nonlearner'
        else:
            i['Type'] = protocol_types[i['Protocol']]
        study_list.append(i)

    current_dir = os.getcwd()

    try:
        os.chdir(dest)
        synapse_utils.export_synapse_studies(study_list, dest, bag_metadata)
    finally:
        os.chdir(current_dir)


study_entities = synapse_utils.get_synapse_studies()
print('Identified %d studies' % len(study_entities))

bag_metadata['ERMRest-Query'] = study_entities.uri
export_files(study_entities, destdir, bag_metadata)
print('Dumped studies')

