import os
import shutil
import tempfile
import pandas as pd
import csv


def get_synapses(synapsefiles, study):
    """
     synapsefile: a HatracStore object
     study: a dictionary that has URLs for the two images, before and after

     returns two pandas that have the synapses in them.
     """

    try:
        # Get a path for a tempory file to store HATRAC results
        path = os.path.join(tempfile.mkdtemp(), 'image')

        # Get the before image from hatrac, be careful in case its missing
        if study['Region 1 URL']:
            synapsefiles.get_obj(study['Region 1 URL'], destfilename=path)
            img1 = pd.read_csv(path)
            img1.drop(img1.index[0], inplace=True)
        else:
            img1 = None

        # Get the after image from hatrac, be careful in case its missing
        if study['Region 2 URL']:
            synapsefiles.get_obj(study['Region 2 URL'], destfilename=path)
            img2 = pd.read_csv(path)
            img2.drop(img2.index[0], inplace=True)
        else:
            img2 = None
    finally:
        shutil.rmtree(os.path.dirname(path))
    return {'Before': img1, 'After': img2, 'Type': study['Type'], 'Study': study['Study'], 'Subject': study['Subject']}


def copy_synapses(objectstore, study):
    """
    Copy the files assoicated with a study into a local directory
    """

    for URL in [study['Region 1 URL'], study['Region 2 URL']]:
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
                        synapse.readline()

                        # now copy the rest of the file...
                        for f in synapse:
                            outfile.write(f)
        finally:
            shutil.rmtree(os.path.dirname(tmpfile))


def export_synapse_studies(objectstore, study_list):
    """
    Export all of the synapse data for every study in the study list.
    Also output a CVS file that contains an index of all of the data.

    The data indes is: StudyID, SubjectID, Study Type, FileNames for Before and After synapses.

    """
    # Create an output directory for synapse files.
    os.makedirs('synapse-studies', mode=0o777, exist_ok=True)
    os.chdir('synapse-studies')

    for study in study_list:
        copy_synapses(objectstore, study)

    with open('studies.csv', 'w', newline='') as csvfile:
        synapsewriter = csv.writer(csvfile)

        # Write out header....
        synapsewriter.writerow(['Study', 'Subject', 'Type', 'Before', 'After'])
        for study in study_list:

            url1 = study['Region 1 URL']
            url2 = study['Region 2 URL']

            filename1 = filename2 = ''
            if url1:
                filename1 = (os.path.basename(url1.split(':')[0]))
            if url2:
                filename2 = (os.path.basename(url2.split(':')[0]))

            synapsewriter.writerow([study['Study'], study['Subject'], study['Type'], filename1, filename2])
