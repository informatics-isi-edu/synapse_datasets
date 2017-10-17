from deriva_common import HatracStore, ErmrestCatalog, get_credential
import synapse_utils
import os


# Need to use Deriva authentication agent before executing this
credential = get_credential("synapse.isrd.isi.edu")

objectstore = HatracStore('https','synapse.isrd.isi.edu',credentials=credential)
catalog = ErmrestCatalog('https','synapse.isrd.isi.edu', 1, credentials=credential)


study_entities = synapse_utils.get_synapse_studies(catalog)
study_uri = study_entities.uri

print('Identified %d studies' % len(study_entities))

study_list = []

protocol_types = {
    'PrcDsy20160101A': 'aversion',
    'PrcDsy20170613A': 'conditioned',
    'PrcDsy20170615A': 'unconditioned',
    'PrcDsy20170613B': 'control'
}

for i in study_entities:
    if protocol_types[i['Protocol']] == 'aversion':
        i['Type'] = 'learner' if i['Learner'] == True else 'nonlearner'
    else:
        i['Type'] = protocol_types[i['Protocol']]
    study_list.append(i)

    # Dump out the synapses to a local directory

destdir = '/Users/carl/Desktop'
current_dir = os.getcwd()

try:
    os.chdir(destdir)
    synapse_utils.export_synapse_studies(objectstore, study_list)
finally:
    os.chdir(current_dir)