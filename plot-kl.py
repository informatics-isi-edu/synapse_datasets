# Plot a study

import pandas as pd
import csv
import plotly as py
import plotly.graph_objs as go


kldir = '/Users/carl/Google (carl@usc.edu)/USC/Projects/Synapse/synapse-code/pointwise_kl'
file = 'groundtruth-control_SynStd8179.csv'

synapses = pd.read_csv(kldir + '/' + file)

py.offline.init_notebook_mode(connected=True)

def plot_divergence(synapses):
    '''
    Create a 3D scatter plot of a study.
    '''
    synapses = go.Scatter3d(
        x=synapses['X'],
        y=synapses['Y'],
        z=synapses['Z'],
        mode='markers',
        marker=dict(
            size=2,
            line=dict(
                color= synapses['pointwise_kl_divergence'],
                colorscale = 'Viridis',
                showscale = True,
                width=0.5
            ),
        opacity=0.8
        )
    )


    data = [synapses]

    layout = go.Layout(
        margin=dict(
            l=0,
            r=0,
            b=0,
            t=0
        )
    )

    fig = go.Figure(data=data, layout=layout)
    py.offline.iplot(fig)