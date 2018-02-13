import os
import shutil
import tempfile
import pandas as pd
import csv
from deriva.core import HatracStore, ErmrestCatalog, get_credential
#import bdbag.bdbag_api

# Configuring the logger for debug level will display the uri's generated by the api
debug = False
if debug:
    import logging
    logger = logging.getLogger('deriva_common.datasets')
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)


def get_synapses(study):
    """
     synapsefile: a HatracStore object
     study: a dictionary that has URLs for the two images, before and after

     returns two pandas that have the synapses in them.
     """
    credential = get_credential("synapse.isrd.isi.edu")
    objectstore = HatracStore('https', 'synapse.isrd.isi.edu', credentials=credential)

    # Get a path for a tempory file to store HATRAC results
    path = os.path.join(tempfile.mkdtemp(), 'image')
    try:
        # Get the before image from hatrac, be careful in case its missing
        if study['BeforeURL']:
            objectstore.get_obj(study['BeforeURL'], destfilename=path)
            img1 = pd.read_csv(path)
            if True:
                img1.drop(img1.index[0], inplace=True)
        else:
            img1 = None

        # Get the after image from hatrac, be careful in case its missing
        if study['AfterURL']:
            objectstore.get_obj(study['AfterURL'], destfilename=path)
            img2 = pd.read_csv(path)
            if True:
                img2.drop(img2.index[0], inplace=True)
        else:
            img2 = None
    finally:
        shutil.rmtree(os.path.dirname(path))
    return {'Before': img1, 'After': img2, 'Type': study['Type'], 'Study': study['Study'], 'Subject': study['Subject']}


def copy_synapse_files(objectstore, study):
    """
    Copy the files associated with a study into a local directory
    """

    for URL in [study['BeforeURL'], study['AfterURL']]:
        try:
            # Get a path for a tempory file to store HATRAC results
            tmpfile = os.path.join(tempfile.mkdtemp(), 'image')

            # Create an output directory for synapse files.
            os.makedirs('synapse-data', mode=0o777, exist_ok=True)

            # Get the before image from hatrac, be careful in case its missing
            if URL:
                objectstore.get_obj(URL, destfilename=tmpfile)

                # Get the file name from the URL
                hatracfilename = (os.path.basename(URL.split(':')[0]))

                # Now copy the file from the tmp directory to where it will end up....
                with open(tmpfile) as synapse:
                    with open('synapse-data/' + hatracfilename, 'w') as outfile:
                        # Write header
                        outfile.write(synapse.readline())

                        # Skip second line
                        f = synapse.readline()
                        if 'saved,parameters' not in f:
                            outfile.write(f)

                        # now copy the rest of the file...
                        for f in synapse:
                            outfile.write(f)
        finally:
            shutil.rmtree(os.path.dirname(tmpfile))


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

        bdbag.bdbag_api.make_bag(dumpdir, metadata=bag_metadata)
        archivefile = bdbag.bdbag_api.archive_bag(dumpdir, 'zip')

        if publish:
            bagstore = HatracStore('https', 'synapse-dev.isrd.isi.edu', credentials=credential)
            hatrac_path = '/hatrac/Data/synapse-{0}'.format(bag_metadata['ERMRest-Snapshot'])
            return bagstore.put_obj(hatrac_path, archivefile)
    finally:
        os.chdir(current_dir)
    return archivefile


def get_synapse_studies(studyset, protocols=None):
    """
    Get the current list of synapse studys.
    :param protocols:
    :return:
    """

    # Need to use Deriva authentication agent before executing this
    credential = get_credential("synapse.isrd.isi.edu")
    catalog = ErmrestCatalog('https', 'synapse.isrd.isi.edu', 1, credentials=credential)

    pb = catalog.getPathBuilder()

    # convenient name for the schema we care about.
    zebrafish = pb.Zebrafish
    synapse = pb.Synapse

    # Lets get some shortcuts for awkward table names.
    cohort_table = zebrafish.tables['Cohort Analysis']
    study_table = zebrafish.tables['Synaptic Pair Study']
    pair_table = zebrafish.tables['Image Pair Study']

    # Build up the path cohort->study->pair->behavior.
    # Make aliases for study and pair instances for later use.
    # We use the left join to make sure we get controls, which will be studies without behaviors.
    path = cohort_table.alias('studyset')\
        .link(zebrafish.tables['Cohort Analysis_Synaptic Pair Study']) \
        .link(study_table.alias('study')) \
        .link(pair_table.alias('pair')) \
        .link(zebrafish.Behavior, join_type='left', on=(pair_table.Subject == zebrafish.Behavior.Subject))

    # Now lets go back an pick up the protocols which are associated with an image.
    # Each image has a protocol step, and from the step we can get the protocol.
    # Use the first image.
    path = path.pair.link(zebrafish.Image.alias('image'), on=path.pair.columns['Image 1'] == zebrafish.Image.ID) \
        .link(synapse.tables['Protocol Step']) \
        .link(synapse.Protocol)

    # Now just pick out the studyset we want.
    path = path.filter(path.studyset.RID == studyset)

        # Subset on a list of protocols
    if not protocols:
        pass

    # Now that we have build up the path, we can retrieve the set of studies and associated values
    study_entities = path.study.entities(Study=path.study.ID,
                                         Subject=path.pair.Subject,
                                         Region1=path.study.columns['Synaptic Region 1'],
                                         Region2=path.study.columns['Synaptic Region 2'],
                                         BeforeURL=path.study.columns['Region 1 URL'],
                                         AfterURL=path.study.columns['Region 2 URL'],
                                         BeforeImageID=path.pair.columns['Image 1'],
                                         AfterImageID=path.pair.columns['Image 2'],
                                         Learner=path.Behavior.columns['Learned?'],
                                         AlignP0=path.image.columns['Align P0 ZYX'],
                                         AlignP1=path.image.columns['Align P1 ZYX'],
                                         AlignP2=path.image.columns['Align P2 ZYX'],
                                         Protocol=path.Protocol.ID )

    return study_entities
