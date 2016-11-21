from copy import deepcopy

import numpy as np
import pandas as pd

from krisk.plot.make_chart import insert_series_data, round_list
from krisk.util import future_warning


def set_bar_line_chart(chart, df, x, c, **kwargs):
    """Construct Bar, Line, and Histogram"""

    data = None
    chart_type = kwargs['type']

    if chart_type in ['bar', 'line']:
        data = get_bar_or_line_data(df, x, c, **kwargs)
        chart.option['xAxis']['data'] = data.index.values.tolist()

    elif chart_type == 'hist':
        chart_type = 'bar'
        data, bins = get_hist_data(df, x, c, **kwargs)
        chart.option['xAxis']['data'] = bins

    if c:
        # append data for every category
        for cat in data.columns:
            insert_series_data(data[cat], x, chart_type, chart, cat)
    else:
        insert_series_data(data, x, chart_type, chart)

    series = chart.option['series']

    ########Provide stacked,annotate, area for bar line hist#################
    d_annotate = {'normal': {'show': True, 'position': 'top'}}

    if c and kwargs['stacked']:
        for s in series:
            s['stack'] = c

            if chart_type == 'line' and kwargs['area']:
                s['areaStyle'] = {'normal': {}}

            if kwargs['annotate'] == 'all':
                s['label'] = deepcopy(d_annotate)

                if chart_type == 'bar':
                    s['label']['normal']['position'] = 'inside'

        if kwargs['type'] in ['line','bar'] and kwargs['full']:
            chart.option['yAxis']['max'] = 1

    if kwargs['annotate'] == 'top':
        series[-1]['label'] = d_annotate
    # TODO: make annotate receive all kinds supported in echarts.

    # Special Bar Condition: Trendline
    if kwargs['type'] == 'bar' and kwargs['trendline']:
        trendline = {'name': 'trendline', 'type': 'line',
                     'lineStyle': {'normal': {'color': '#000'}}}

        if c and kwargs['stacked']:
            trendline['data'] = [0] * len(series[-1]['data'])
            trendline['stack'] = c
        elif c is None:
            trendline['data'] = series[0]['data']
        else:
            raise AssertionError('Trendline must either stacked category,'
                                 ' or not category')

        series.append(trendline)

    # Special Line Condition: Smooth
    if kwargs['type'] == 'line' and kwargs['smooth']:
        for s in series:
            s['smooth'] = True


    # Special Histogram Condition: Density
    #TODO NEED IMPROVEMENT!
    if kwargs['type'] == 'hist' and kwargs['density']:
        
        density = {'name':'density', 'type': 'line', 'smooth': True,
                   'lineStyle': {'normal': {'color': '#000'}}}
        chart.option['xAxis']['boundaryGap'] = False

        # The density have to be closed at zero. So all of xAxis and series
        # must be updated to incorporate the changes
        chart.option['xAxis']['data'] = [0] + chart.option['xAxis']['data'] + [0]

        for s in series:
            s['data'] = [0] + s['data']

        if c and kwargs['stacked']:
            density['data'] = [0] + round_list(data.sum(axis=1)) + [0]
        elif c is None:
            density['data'] =  [0] + round_list(data) + [0] 
        else:
            raise AssertionError('Density must either stacked category, '
                                 'or not category')

        series.append(density)   


def get_bar_or_line_data(df, x, c, y, **kwargs):
    """Get Bar and Line manipulated data"""
    
    if c and y:
        data = df.pivot_table(
                index=x,
                values=y,
                columns=c,
                aggfunc=kwargs['how'],
                fill_value=None)
    elif c and y is None:
        data = pd.crosstab(df[x], df[c])
    elif c is None and y:
        data = df.groupby(x)[y].agg(kwargs['how'])
    else:
        data = df[x].value_counts()

    # Specify sort_on and order method
    sort_on = kwargs['sort_on']
    descr_keys = pd.Series([0]).describe().keys().tolist()
    
    if isinstance(sort_on, str):
        assert sort_on in ['index','values'] + descr_keys

    if sort_on == 'index':
        data.sort_index(inplace=True, ascending=kwargs['ascending'])
    else:
        if sort_on != 'values':
            val_deviation = sort_on(data) if callable(sort_on) else sort_on
            data = data - val_deviation
        if c:
            assert kwargs['sort_c_on'] is not None
            (data.sort_values(kwargs['sort_c_on'],
                              inplace=True,
                              ascending=kwargs['ascending']))
        else:
            data.sort_values(inplace=True, ascending=kwargs['ascending'])

    # Stacked when category
    if c and kwargs['stacked'] and kwargs['full']:
        data = data.div(data.sum(1),axis=0)

    return data


def get_hist_data(df, x, c, **kwargs):
    """Get Histogram manipulated data"""

    y_val, x_val = np.histogram(
        df[x], bins=kwargs['bins'], normed=kwargs['normed'])
    bins = x_val.astype(int).tolist()

    if c:
        data = pd.DataFrame()
        for cat, sub in df.groupby(c):
            data[cat] = (pd.cut(sub[x], x_val).value_counts(
                sort=False, normalize=kwargs['normed']))
    else:
        data = pd.Series(y_val)

    return data, bins


def set_barline(chart, df, x, **kwargs):
    """Set Bar-Line charts"""

    ybar = kwargs['ybar']
    yline = kwargs['yline']

    if kwargs['is_distinct'] is True:
        data = df[[x, ybar, yline]].drop_duplicates(subset=[x]).copy()
        data.index = data.pop(x)
    else:
        data = (df
                .groupby(x)
                .agg({ybar: kwargs['bar_aggfunc'],
                      yline: kwargs['line_aggfunc']}))

        assert kwargs['sort_on'] in ['index', 'ybar', 'yline']
        if kwargs['sort_on'] == 'index':
            data.sort_index(ascending=kwargs['ascending'], inplace=True)
        else:
            data.sort_values(kwargs[kwargs['sort_on']],
                             ascending=kwargs['ascending'], inplace=True)

    def get_series(col, type): return dict(name=col, type=type,
                                           data=round_list(data[col]))
    chart.option['series'] = [
        get_series(ybar, 'bar'),
        dict(yAxisIndex=1, **get_series(yline, 'line'))
    ]

    if kwargs['hide_split_line'] is True:
        def get_yaxis(col): return {'name': col, 'splitLine': {'show': False}}
        chart.option['yAxis'] = [get_yaxis(ybar), get_yaxis(yline)]

    if kwargs['style_tooltip'] is True:
        chart.set_tooltip_style(axis_pointer='shadow', trigger='axis')

    chart.option['xAxis']['data'] = data.index.values.tolist()
    return data


def set_waterfall(chart, s, **kwargs):

    # TODO
    # * Set annotation
    # * Find a way to naming index and value
    # * Possible customize tooltip solution

    invisible_bar = {'name': '',
                     'type': 'bar',
                     'stack': 'stack',
                     "itemStyle": {
                         "normal": {
                             "barBorderColor": 'rgba(0,0,0,0)',
                             "color": 'rgba(0,0,0,0)'
                         },
                         "emphasis": {
                             "barBorderColor": 'rgba(0,0,0,0)',
                             "color": 'rgba(0,0,0,0)'
                         }
                     }}
    visible_bar = {'type': 'bar', 'stack': 'stack'}

    invisible_series = s.cumsum().shift(1).fillna(0)

    if (invisible_series >= 0).all() is np.False_:
        raise NotImplementedError("cumulative sum should be positive")

    invisible_series = np.where(s < 0,
                                invisible_series - s.abs(),
                                invisible_series)
    invisible_bar['data'] = round_list(invisible_series)
    chart.option['series'].append(invisible_bar)

    def add_bar(series, name):
        """Append bar to chart series"""

        bar = deepcopy(visible_bar)
        bar['name'] = name
        bar['data'] = round_list(series)
        chart.option['series'].append(bar)

    if kwargs['color_coded']:

        boolean_pivot = (pd.DataFrame(s)
                         .pivot_table(values=s.name,
                                      index=s.index,
                                      columns=s > 0)
                         .abs()
                         .round(3)
                         .fillna('-'))

        add_bar(boolean_pivot[True], kwargs['up_name'])
        add_bar(boolean_pivot[False], kwargs['down_name'])
    else:
        add_bar(s.abs(), s.name)

    chart.option['xAxis']['data'] = s.index.values.tolist()

    return s








    


