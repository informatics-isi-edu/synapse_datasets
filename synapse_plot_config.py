import matplotlib
from matplotlib import cm
import plotly.graph_objs as go

import random
from collections import OrderedDict
import numpy as np


# Generate shades of blue and orange for the plots and assign colors to the different trace types.
def matplotlib_to_plotly(cmap, pl_entries):
    h = 1.0 / (pl_entries - 1)
    pl_colorscale = []

    for k in range(pl_entries):
        c = list(map(np.uint8, np.array(cmap(k * h)[:3]) * 255))
        pl_colorscale.append('rgb' + str((c[0], c[1], c[2])))

    return pl_colorscale


colorindex = 0


def trace_color(trace):
    global colorindex
    shades = 256

    blues_cmap = matplotlib.cm.get_cmap('Blues')
    oranges_cmap = matplotlib.cm.get_cmap('Oranges')

    blues = matplotlib_to_plotly(blues_cmap, shades)
    oranges = matplotlib_to_plotly(oranges_cmap, shades)

    if trace == 'AlignmentPts':
        color = 'black'
    elif 'Before' in trace:
        color = oranges[random.randrange(125, 256)]
    else:
        color = blues[random.randrange(128, 256)]
    return color


def position_annotations(minx, miny, minz, maxx, maxy, maxz):
    annotations = [
        dict(
            showarrow=False,
            x=minx, y=(maxy - miny) / 2 + miny, z=(maxz - minz) / 2 + minz,
            text="Medial",
            font=dict(color="red", size=12)
        ),
        dict(
            showarrow=False,
            x=maxx, y=(maxy - miny) / 2 + miny, z=(maxz - minz) / 2 + minz,
            text="Lateral",
            font=dict(color="red", size=12),
        ),
        dict(
            showarrow=False,
            x=(maxx - minx) / 2 + minx, y=miny, z=(maxz - minz) / 2 + minz,
            text="Posterior",
            opacity=0.7,
            font=dict(color="green", size=12),
        ),
        dict(
            showarrow=False,
            x=(maxx - minx) / 2 + minx, y=maxy, z=(maxz - minz) / 2 + minz,
            text="Anterior",
            font=dict(color="green", size=12),
        ),
        dict(
            showarrow=False,
            x=(maxx - minx) / 2 + minx, y=(maxy - miny) / 2 + miny, z=minz,
            text="Dorsal",
            font=dict(color="blue", size=12),
        ),
        dict(
            showarrow=False,
            x=(maxx - minx) / 2 + minx, y=(maxy - miny) / 2 + miny, z=maxz,
            text="Ventral",
            font=dict(color="blue", size=12),
        )]
    return annotations


def position_layout(minx, miny, minz, maxx, maxy, maxz):
    layout = go.Layout(
        height=900,
        showlegend=True,
        scene=dict(
            xaxis=dict(title='X Axis',
                       range=[minx, maxx],
                       color='red'),
            yaxis=dict(title='Y Axis',
                       range=[miny, maxy],
                       color='green'),
            zaxis=dict(title='Z Axis',
                      range=[minz, maxz],
                       color='blue', ),

            camera=dict(up=dict(x=0, y=0, z=1)),
            aspectmode='cube',
            domain=dict(y=[0,.9]),
        #    dragmode='turntable',
            annotations=position_annotations(minx, miny, minz, maxx, maxy, maxz)
        )
    )
    return layout


def trace_masks(study_map, trace_map, type_map):
    """
    Walk over the maps of studyname->index, tracename->index and type->index and create masks for the buttons.

    :param study_map: a dictionary in the form SName: {TraceName : [list of trace-indexes]}
    :param trace_map: is a dictionary in the from TName: {SName : [list of trace-indexes]} where TName is the one of
    AlignedPairedBefore, AlignedUnpairedBefore, ....
    :param type_map: a dictionary whose keys are study IDs and whose values are the type of study (learner, nonlearner..)
    :return:
    """
    study = OrderedDict()
    studyset = {}
    trace = OrderedDict()

    # Figure out how many traces we have.
    trace_cnt = 0
    for s, v in study_map.items():
        for t, idx in v.items():
            trace_cnt = max(trace_cnt, idx)
    trace_cnt = trace_cnt + 1

    type_set = {v for k, v in type_map.items()}
    study_types = ['all']
    if 'learner' in type_set:
        study_types.append('learner')
    if 'nonlearner' in type_set:
       study_types.append('nonlearner')
    study_types.extend([i for i in type_set if 'control' in i])

    for i in study_types:
        studyset[i] = {j: [False] * trace_cnt for j in ['all', 'before', 'after']}

    # create mask for each trace
    for t, v in trace_map.items():
        trace[t] = {}
        for i in study_types:
            trace[t][i] = [False] * trace_cnt

        for s, idx in v.items():
            trace[t]['all'][idx] = True
            trace[t][type_map[s]][idx] = True

    # Create masks for each study.
    for s, v in study_map.items():
        study[s] = {i: [False] * trace_cnt for i in ['all', 'before', 'after']}
        for t, idx in v.items():
            study[s]['all'][idx] = True
            studyset['all']['all'][idx] = True
            studyset[type_map[s]]['all'][idx] = True

            if 'Before' in t:
                study[s]['before'][idx] = True
                studyset['all']['before'][idx] = True
                studyset[type_map[s]]['before'][idx] = True
            elif 'After' in t:
                study[s]['after'][idx] = True
                studyset['all']['after'][idx] = True
                studyset[type_map[s]]['after'][idx] = True

    return {'trace': trace, 'study': study, 'studyset': studyset}


def step_buttons(plotmode, masks, study_types, step=None, showlegend=True, skipall=False, title = ""):
    button_list = []
    plotmode = plotmode.lower()
    study_types = ['all'] + study_types

    if plotmode == 'trace':
        for i in study_types:
            l = i.capitalize()
            button_list.append(dict(args=[{'visible': masks['trace'][step][i]}], label=l, method='restyle'))
            updatemenus = list([
                dict(buttons=button_list, direction='left', showactive=True, type='buttons',
                     xanchor='left', yanchor='top', x=0, y=1.05, )]
            )
    elif plotmode == 'study':
        button_list.append(dict(args=[{'visible': masks['study'][step]['all']}], label='All', method='update'))
        button_list.append(dict(args=[{'visible': masks['study'][step]['before']}], label='Before', method='update'))
        button_list.append(dict(args=[{'visible': masks['study'][step]['after']}], label='After', method='update'))
        updatemenus = list([
            dict(buttons=button_list, direction='left', showactive=True, type='buttons',
                 xanchor='left', yanchor='top', x=0, y=1.05, )]
        )
    else:  # studyset
        # split types into controls and others...
        controls = [i for i in study_types if 'control' in i]
        others = [i for i in study_types if not 'control' in i]

        # First lay out the buttons for all, learners and nonlearners....
        y=1.05
        for i in others:
            l = i.capitalize()
            if skipall and i == 'all':
                continue
            smask = masks['studyset'][i]
            button_list.append(dict(args=[{'visible': smask['all']}, {'title' : title + l + ' All'}],
                                    label=l + ' All', method='update'))
            button_list.append(dict(args=[{'visible': smask['before']}, {'title' : title + l + ' Before'}],
                                    label='Before', method='update'))
            button_list.append(dict(args=[{'visible': smask['after']}, {'title' : title + l + ' After'}],
                                    label='After', method='update'))
            updatemenus = list([
                dict(buttons=button_list, direction='left', showactive=False, type='buttons',
                     xanchor='left', yanchor='top', x=0, y=y, )]
            )

        # Now put in buttons for controls....
        y = y - .07
        for i in controls:
            smask = masks['studyset'][i]
            control_buttons = []
            l = i.capitalize()
            control_buttons.append(dict(args=[{'visible': smask['all']}, {'title' : title + l + ' All'}],
                                        label=l + ' All', method='update'))
            control_buttons.append(dict(args=[{'visible': smask['before']}, {'title' : title + l + ' All'}],
                                        label='Before', method='update'))
            control_buttons.append(dict(args=[{'visible': smask['after']}, {'title' : title + l + ' All'}],
                                        label='After', method='update'))
            updatemenus.append(
                dict(buttons=control_buttons, direction='left', showactive=False, type='buttons',
                     xanchor='left', yanchor='top', x=0, y=y, ))
            y = y - .07

    if showlegend:
        updatemenus.append(
            dict(
                buttons=list([
                    dict(args=[{'showlegend': True}], label='Legend on', method='update'),
                    dict(args=[{'showlegend': False}], label='Legend off', method='update')
                ]),
                direction='left',
                showactive=True,
                type='buttons',
                xanchor='left',
                y=1.1,
                x=0,
                yanchor='top'
            )
        )

    return updatemenus


def plot_steps(masks, study_types):
    trace = []
    study = []
    # create steps for each trace
    for t, m in masks['trace'].items():
        trace.append(dict(label='{0}'.format(t),
                          args=[{'visible': m['all']}, {'updatemenus': step_buttons('trace', masks, study_types, t)}],
                          method='update'))

    # Now loop over list of study names and create buttons.
    for s, m in masks['study'].items():
        study.append(dict(label='{0}'.format(s),
                          args=[{'visible': m['all']}, {'updatemenus': step_buttons('study', masks, study_types, s)}],
                          method='update'))
    return study, trace

def studytypes(studylist):
    # Get the list of study types, and order as learner, nonlearner, controls....
    type_set = {s['Type'] for s in studylist}
    study_types = []
    if 'learner' in type_set:
        study_types.append('learner')
    if 'nonlearner' in type_set:
        study_types.append('nonlearner')
    study_types.extend([i for i in type_set if 'control' in i])
    return(study_types)


def plot_synapses(studylist,
                  tracelist=['PairedBefore', 'PairedAfter', 'UnpairedBefore', 'UnpairedAfter'],
                  plotmode='Study',
                  radius=False,
                  centroid=False):
    # Change this if you want the point sizes in the plots to be different
    pt_size = 4

    plotmode = plotmode.lower()
    # Use the smallest available radius as the default if one is not provided.
    radius = radius if radius else min(studylist[0][tracelist[0]])

    # Get the list of study types, and order as learner, nonlearner, controls....
    type_set = {s['Type'] for s in studylist}
    study_types = studytypes(studylist)

    if centroid:
        centroidlist = []
        for t in tracelist:
            if t != 'AlignmentPts':
                centroidlist.append(t + 'Centroid')
        tracelist = tracelist + centroidlist
    data = []

    maxx, maxy, maxz, = [-float('inf')] * 3
    minx, miny, minz = [float('inf')] * 3

    # We would like studies and traces to remain in user specified order....
    study_map, trace_map = [OrderedDict(), OrderedDict()]
    for s in studylist:
        study_map[s['Study']] = OrderedDict()
    for t in tracelist:
        trace_map[t] = OrderedDict()

    type_map = {}
    for s in studylist:
        sname = s['Study']
        for idx, t in enumerate(tracelist):
            synapse_data = s[t][radius]['Data']

            maxx = max(maxx, synapse_data['x'].max())
            maxy = max(maxy, synapse_data['y'].max())
            maxz = max(maxz, synapse_data['z'].max())
            minx = min(minx, synapse_data['x'].min())
            miny = min(miny, synapse_data['y'].min())
            minz = min(minz, synapse_data['z'].min())

            x, y, z = list(synapse_data['x']), list(synapse_data['y']), list(synapse_data['z'])

            if 'Centroid' in t:
                symbol = 'cross'
                size = pt_size + 4
            elif 'AlignmentPts' in t:
                symbol = 'square'
                size = pt_size + 4
            else:
                symbol = 'circle'
                size = pt_size
            color = trace_color(t)
            trace_synapses = go.Scatter3d(
                visible=False,
                x=x, y=y, z=z,
                text='{0} Synapse'.format(sname),
                name='{0} {1}'.format(t, sname),
                mode='markers',
                marker=dict(
                    symbol=symbol,
                    size=size, color=color, opacity=0.5,
                    line=dict(color=color, width=0.8))
            )

            study_map[sname][t] = len(data)
            type_map[sname] = s['Type']
            trace_map[t][sname] = len(data)
            data.append(trace_synapses)
            layout = position_layout(minx, miny, minz, maxx, maxy, maxz)
            layout['title'] = 'Synapses'

    masks = trace_masks(study_map, trace_map, type_map)
    if plotmode == 'studyset':
        layout['updatemenus'] = step_buttons(plotmode, masks, study_types)

        for i in data:
            i['visible'] = True
    else:
        sliders = [dict(
            active=0,
            currentvalue={"visible": True},
            len=.9,
        )]
        (study_steps, trace_steps) = plot_steps(masks, study_types)

        # Get the mask from the first step, which is in the 2nd element of the args list..
        if plotmode == 'study':
            # Make the first study visible
            sname = studylist[0]['Study']
            mask = masks['study'][sname]['all']
            sliders[0]['steps'] = study_steps
            layout['updatemenus'] = step_buttons(plotmode, masks, study_types, sname)
        else:
            mask = masks['trace'][tracelist[0]]['all']
            sliders[0]['steps'] = trace_steps
            layout['updatemenus'] = step_buttons(plotmode, masks, study_types, tracelist[0])

        # Set first step to be visible
        for i in range(len(data)):
            data[i]['visible'] = mask[i]
        layout['sliders'] = sliders
    fig = dict(data=data, layout=layout)
    return fig
