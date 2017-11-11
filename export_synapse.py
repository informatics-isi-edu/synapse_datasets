import synapse_utils
from deriva.core import ErmrestCatalog, get_credential
import deriva.core.versioned_catalog as vc

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

destdir = '/Users/carl/Desktop'

# Get the entity list of studies.....
study_entities = synapse_utils.get_synapse_studies()
print('Identified %d studies' % len(study_entities))

# This is a hack until we get get right version support in PathBuilder
ermrest_version = vc.current_catalog_version(
    ErmrestCatalog('https', 'synapse.isrd.isi.edu', 1,
                   get_credential('synapse.isrd.isi.edu')))

# Set some additional bag metadata
bag_metadata['ERMRest-Query'] = vc.versioned_path(study_entities.uri, ermrest_version)
bag_metadata['ERMRest-Snapshot'] = ermrest_version

# now dump out the bag and publish to hatrac
archive = synapse_utils.synapses_to_bag(study_entities, destdir, protocol_types, bag_metadata)

print('Dumped studies')
