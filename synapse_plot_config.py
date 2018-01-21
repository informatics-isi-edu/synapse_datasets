import matplotlib
from matplotlib import cm
import plotly.graph_objs as go

import random
from  collections import OrderedDict
import numpy as np

# Generate shades of blue and orange for the plots and assign colors to the different trace types.
def matplotlib_to_plotly(cmap, pl_entries):
    h = 1.0 / (pl_entries - 1)
    pl_colorscale = []

    for k in range(pl_entries):
        C = list(map(np.uint8, np.array(cmap(k * h)[:3]) * 255))
        pl_colorscale.append('rgb' + str((C[0], C[1], C[2])))

    return pl_colorscale


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

            aspectmode='cube',
            dragmode='turntable',
            annotations=position_annotations(minx, miny, minz, maxx, maxy, maxz)
        )
    )
    return layout


def trace_masks(study_map, trace_map):
    all = OrderedDict()
    before = OrderedDict()
    after = OrderedDict()
    trace = OrderedDict()

    # Figure out how many traces we have.
    trace_cnt = 0
    for s, v in study_map.items():
        for t, idx in v.items():
            trace_cnt = max(trace_cnt, idx)
    trace_cnt = trace_cnt + 1

    # create mask for each trace
    for t, v in trace_map.items():
        trace_mask = [False] * trace_cnt
        for s, idx in v.items():
            trace_mask[idx] = True
        trace[t] = trace_mask

    # Create masks for each study.  We want the studies to be in the same order as
    for s, v in study_map.items():
        all_mask = [False] * trace_cnt
        before_mask = [False] * trace_cnt
        after_mask = [False] * trace_cnt
        for t, idx in v.items():
            all_mask[idx] = True
            if 'Before' in t:
                before_mask[idx] = True
            elif 'After' in t:
                after_mask[idx] = True
        all[s] = all_mask
        before[s] = before_mask
        after[s] = after_mask

    return {'all': all, 'before': before, 'after': after, 'trace': trace}


def step_buttons(study, masks):
    updatemenus = list([
        dict(
            buttons=list([
                dict(
                    args=[{'showlegend': True}],
                    label='Legend on',
                    method='relayout'
                ),
                dict(
                    args=[{'showlegend': False}],
                    label='Legend off',
                    method='relayout'
                ),
            ]),
            direction='left',
            showactive=True,
            type='buttons',
            xanchor='left',
            y=1.1,
            x=0,
            yanchor='top'
        ),
        dict(
            buttons=list([
                dict(
                    args=[{
                        'visible': masks['all'][study],
                    }],
                    label='All',
                    method='restyle'
                ),
                dict(
                    args=[{
                        'visible': masks['before'][study],
                    }],
                    label='Before',
                    method='restyle'
                ),
                dict(
                    args=[{
                        'visible': masks['after'][study],
                    }],
                    label='After',
                    method='restyle'
                )
            ]),
            direction='left',
            showactive=True,
            type='buttons',
            xanchor='left',
            x=0,
            y=1.05,
            yanchor='top'
        ),
    ])
    return updatemenus


def plot_steps(masks):
    trace = []
    study = []
    # create steps for each trace
    for t, trace_mask in masks['trace'].items():
        trace.append(dict(label='{0}'.format(t),
                          args=[{'visible': trace_mask}],
                          method='restyle'))
    # Now loop over list of study names and create buttons.
    for s, all_mask in masks['all'].items():
        study.append(dict(label='{0}'.format(s),
                          args=[{'visible': all_mask}, {'updatemenus': step_buttons(s, masks)}],
                          method='update'))
    return (study, trace)


def plot_synapses(studylist,
                  tracelist=['PairedBefore', 'PairedAfter', 'UnpairedBefore', 'UnpairedAfter'],
                  slider='Study',
                  radius=False,
                  centroid=False):
    # Change this if you want the point sizes in the plots to be different
    pt_size = 4

    # Use the smallest available radius as the default if one is not provided.
    radius = radius if radius else min(studylist[0][tracelist[0]])

    if centroid == True:
        centroidlist = []
        for t in tracelist:
            if t != 'AlignmentPts':
                centroidlist.append(t + 'Centroid')
        tracelist = tracelist + centroidlist
    data = []

    maxx, maxy, maxz, minx, miny, minz = -float('inf'), -float('inf'), -float('inf'), float('inf'), float('inf'), float(
        'inf')

    # We would like studies and traces to remain in user specified order....
    study_map = OrderedDict()
    trace_map = OrderedDict()
    for s in studylist:
        study_map[s['Study']] = OrderedDict()
    for t in tracelist:
        trace_map[t] = OrderedDict()

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
            trace_map[t][sname] = len(data)
            data.append(trace_synapses)
            layout = position_layout(minx, miny, minz, maxx, maxy, maxz)
            layout['title'] = 'Synapses'

    masks = trace_masks(study_map, trace_map)
    if slider is False:
        layout['updatemenus'] = step_buttons(studylist[0]['Study'], masks)
        for i in data:
            i['visible'] = True
    else:
        sliders = [dict(
            active=0,
            currentvalue={"visible": True},
            len=.9,
        )]
        (study_steps, trace_steps) = plot_steps(masks)

        # Get the mask from the first step, which is in the 2nd element of the args list..
        if slider == 'Study':
            # Make the first study visible
            mask = masks['all'][studylist[0]['Study']]
            sliders[0]['steps'] = study_steps
            layout['updatemenus'] = step_buttons(studylist[0]['Study'], masks)
        else:
            mask = masks['trace'][tracelist[0]]
            sliders[0]['steps'] = trace_steps

        # Set first step to be visible
        for i in range(len(data)):
            data[i]['visible'] = mask[i]
        layout['sliders'] = sliders
    fig = dict(data=data, layout=layout)
    return fig
