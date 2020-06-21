import re
import pandas as pd
import datetime as dt
from sqlalchemy import create_engine

import dash
import dash_table
from dash.dependencies import Input, Output
import dash_core_components as dcc
import dash_html_components as html
from dash_table.Format import Format


ENGINE = create_engine("postgresql://korsedo_db:ADeL23099114!@134.209.91.36:5432/betting_db")

sql = '''
SELECT *
FROM odds_archive
WHERE match_dt < date(now()) + 15 or home_odds is not null
'''
DATA = pd.read_sql(sql, con=ENGINE)
DATA['match_dt'] = pd.to_datetime(DATA['match_dt'])
DATA['country'] = DATA['match_link'].apply(lambda s: re.findall(r'(?<=soccer\/)(.*?)(?=\/)', s)[0])
DATA['match'] = DATA['home_name'] + ' vs ' + DATA['away_name']

TOP_COUNTRIES = [
    'england',
    'spain',
    'italy',
    'france',
    'germany',
    'turkey',
    'europe'
]

def stripe_rows(row_ix):
    if row_ix % 2 == 0:
        return 'rgb(248, 248, 248)'
    else:
        return 'rgb(255, 255, 255)'

def get_outcome(score):
    if score == '-:-':
        return None
    else:
        home_goals, away_goals = score.split(':')
        if home_goals > away_goals:
            return 'home'
        elif away_goals > home_goals:
            return 'away'
        else:
            return 'draw'

def odds_2_decimal(odds):
    if isinstance(odds, int) or isinstance(odds, float) and odds > 0:
        return '{0:.2f}'.format(odds)
    else:
        return '-'

def odds_change_direction(odds, open_odds):
    try:
        if float(odds) > float(open_odds):
            return '\u25B4' + odds
        elif float(open_odds) > float(odds):
            return '\u25BE' + odds
        else:
            return odds
    except ValueError:
        return odds

def team_odds_tab(match_link, side):
    if side == 'home':
        team_id = DATA.query(f"match_link == '{match_link}'")['home_id'].iloc[0]
    else:
        team_id = DATA.query(f"match_link == '{match_link}'")['away_id'].iloc[0]
 
    df = DATA.query(f"home_id == '{team_id}' or away_id == '{team_id}'").sort_values('match_dt', ascending=False)
    df = df.reset_index()
    # embed match link in match date
    df['match_dt'] = '**[' + df['match_dt'].dt.strftime('%d.%m.%Y') + '](' + df['match_link'] + ')**'

    df['match_outcome'] = df['final_score'].apply(get_outcome)
    df['result'] = '' # empty col to color cell according to match result  win, draw, loss | green, yellow, red

    # conver odds to float with 2 decimal
    odds_cols = ['home_odds','draw_odds', 'away_odds']
    df[odds_cols] = df[odds_cols].applymap(odds_2_decimal)
    
    # add odds change direction symbol
    df['home_odds'] = df.apply(lambda row: odds_change_direction(row['home_odds'], row['home_open_odds']), axis=1)
    df['draw_odds'] = df.apply(lambda row: odds_change_direction(row['draw_odds'], row['draw_open_odds']), axis=1)
    df['away_odds'] = df.apply(lambda row: odds_change_direction(row['away_odds'], row['away_open_odds']), axis=1)

    cols = ['result', 'match_dt', 'final_score', 'home_name', 'away_name', 'league', 'home_odds',
            'draw_odds', 'away_odds', 'total', 'handicap']
    tooltip_data = []
    style_data_conditional = []
    for row_ix, row in df.iterrows():
        tooltip_data.append(
            {f'{side}_odds': str(df.loc[row_ix, f'{side}_open_odds']) for side in ['home', 'draw', 'away']}
        )
        
        for col in cols:
            color = 'rgb(0, 0, 0)'
            padding = '2px 4px'
            font_size = 14
            font_weight = 'normal'

            if col == 'home_name' and row['home_id'] == team_id:
                font_weight = 'bold'
            elif col == 'away_name' and row['away_id'] == team_id:
                font_weight = 'bold'

            if col == 'league':
                font_size = 12

            if col == 'final_score':
                font_size = 15
                font_weight = 'bold'
                padding = '2px 12px'

            if col == 'total' or col == 'handicap':
                font_size = 13

            if row['match_link'] == match_link: # to highlight selected match
                bg_color = 'rgb(204, 255, 255)'
            else:
                bg_color = stripe_rows(row_ix) # stripe other matches

            # applies only for finished matches
            if col == 'home_odds':
                if row['match_outcome'] == 'home':
                    bg_color = 'rgb(255, 255, 204)'
                if not row['pinnacle']: # gray background for not pinnacle odds
                    color = 'rgb(192, 192, 192)'
            elif col == 'draw_odds':
                if row['match_outcome'] == 'draw':
                    bg_color = 'rgb(255, 255, 204)'
                if not row['pinnacle']:
                    color = 'rgb(192, 192, 192)'
            elif col == 'away_odds':
                padding = '2px 12px'
                if row['match_outcome'] == 'away':
                    bg_color = 'rgb(255, 255, 204)'
                if not row['pinnacle']:
                    color = 'rgb(192, 192, 192)'

            # color result column
            if col == 'result' and row['match_outcome']:
                padding = '2px 2px'
                if row['match_outcome'] == 'home' and row['home_id'] == team_id: # check if selected team won at home
                    bg_color = 'rgb(102,255,102)'
                elif row['match_outcome'] == 'away' and row['away_id'] == team_id: # check if selected team won away
                    bg_color = 'rgb(102,255,102)'
                elif row['match_outcome'] == 'draw':
                    bg_color = 'rgb(255,165,0)'
                else:
                    bg_color = 'rgb(255,51,51)'
            
            style_data_conditional.append(
                {
                    'if': {"row_index": row_ix, 'column_id': col},
                    'backgroundColor': bg_color,
                    'color': color,
                    'padding': padding,
                    'fontSize': font_size,
                    'fontWeight': font_weight
                }
            )

    return df[cols].to_dict('records'), tooltip_data, style_data_conditional


external_stylesheets = [
    'https://codepen.io/chriddyp/pen/bWLwgP.css',
    'https://codepen.io/amyoshino/pen/jzXypZ.css'  # Boostrap CSS
]


app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

app.config.suppress_callback_exceptions = True

app.layout = html.Div([
    # header
    html.Div([
        html.Div([
            dcc.RadioItems(
                id='odds-margin-button',
                options=[
                    {'label': 'ON True Odds', 'value': 'on'},
                    {'label': 'OFF True Odds', 'value': 'off'},
                ],
                value='off'
            )
        ], className= 'one columns', style={'marginLeft': 100}),

        html.Div([
            dcc.RadioItems(
                id='countries-button',
                options=[
                    {'label': 'TOP Countries', 'value': 'top'},
                    {'label': 'All Countries', 'value': 'all'},
                ],
                value='top'
            )
        ], className= 'one columns', style={'marginLeft': 50}),

         html.Div([
            dcc.Dropdown(
                id='countries-dropdown',
                value='spain',
                style=dict(width = '250px')
            )
         ], className= 'one columns', style={'marginLeft': 100}),
        
         html.Div([
            dcc.Dropdown(
                id='leagues-dropdown',
                style=dict(width = '100px')
            )
         ], className= 'one columns', style={'marginLeft': 100}),

         html.Div([
            dcc.Dropdown(
                id='matches-dropdown',
                style=dict(width = '400px')
            )
         ], className= 'one columns', style={'marginLeft': 150})
        
        
    ], className="row 1", style={'marginTop': 30, 'marginBottom': 15}),

    # tables
    html.Div([
        html.Div([
            dash_table.DataTable(
                id='table-home-side',
                columns=[
                    {'name': ' ', 'id': 'result'},
                    {'name': 'League', 'id': 'league'},
                    {'name': 'Home', 'id': 'home_name'},
                    {'name': 'Away', 'id': 'away_name'},
                    {'name': 'Date', 'id': 'match_dt', 'presentation':'markdown'},
                    {'name': 'Score', 'id': 'final_score'},
                    {'name': 'Home', 'id': 'home_odds'},
                    {'name': 'Draw', 'id': 'draw_odds'},
                    {'name': 'Away', 'id': 'away_odds'},
                    {'name': 'AH', 'id': 'handicap'},
                    {'name': 'O/U', 'id': 'total'}
                ],
                style_cell={'height': '20px', 'textAlign': 'center',
                            'textOverflow': 'ellipsis', 'fontFamily': 'Open Sans'},
                style_header = {'display': 'none'},
                style_as_list_view = True
            )
        ], className= 'four columns', style={'marginLeft': 30}),

        html.Div([
            dash_table.DataTable(
                id='table-away-side',
                columns=[
                    {'name': ' ', 'id': 'result'},
                    {'name': 'League', 'id': 'league'},
                    {'name': 'Home', 'id': 'home_name'},
                    {'name': 'Away', 'id': 'away_name'},
                    {'name': 'Date', 'id': 'match_dt', 'presentation':'markdown'},
                    {'name': 'Score', 'id': 'final_score'},
                    {'name': 'Home', 'id': 'home_odds'},
                    {'name': 'Draw', 'id': 'draw_odds'},
                    {'name': 'Away', 'id': 'away_odds'},
                    {'name': 'AH', 'id': 'handicap'},
                    {'name': 'O/U', 'id': 'total'}
                ],
                style_cell={'height': '20px', 'textAlign': 'center',
                            'textOverflow': 'ellipsis', 'fontFamily': 'Open Sans'},
                style_header = {'display': 'none'},
                style_as_list_view = True
            )
        ], className= 'four columns', style={'marginLeft': 280})
    ], className="row 2", style={'marginTop': 30, 'marginBottom': 15}),
]
)


@app.callback(
    Output('countries-dropdown', 'options'),
    [Input('countries-button', 'value')])
def update_country_list(country_button):
    if country_button == 'top':
        countries = sorted(DATA[DATA['country'].isin(TOP_COUNTRIES)]['country'].unique())
    else:
        countries = sorted(DATA['country'].unique())
    values = [{'label':i, 'value':i} for i in countries]
    return values

@app.callback(
    [Output('leagues-dropdown', 'options'),
     Output('leagues-dropdown', 'value')],
    [Input('countries-dropdown', 'value')])
def update_league_list(country):
    leagues = sorted(DATA.query(f"country == '{country}'")['league'].unique(), key=lambda s: s[-1])
    values = [{'label':i, 'value':i} for i in leagues]
    return values, leagues[0]


@app.callback(
    Output('matches-dropdown', 'options'),
    [Input('countries-dropdown', 'value'),
     Input('leagues-dropdown', 'value')])
def update_match_list(country, league):
    matches = DATA[DATA['match_dt'] >= dt.datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)]
    matches = matches.query(f"country == '{country}' and league == '{league}' and finished == False")
    matches = matches.sort_values('match_dt')
    matches = matches[['match', 'match_dt', 'match_link']]
    values = [{'label':m[1].date().strftime('%d.%m') + ' | ' + m[0], 'value': m[2]} for m in matches.values]
    return values


@app.callback(
    [Output('table-home-side', 'data'), Output('table-away-side', 'data'),
     Output('table-home-side', 'tooltip_data'), Output('table-away-side', 'tooltip_data'),
     Output('table-home-side', 'style_data_conditional'), Output('table-away-side', 'style_data_conditional')],
    [Input('matches-dropdown', 'value')])
def update_odds_tab(match_link):
    if match_link is None:
        return [None] * 6
    home_data, home_tooltip_data, home_style_data = team_odds_tab(match_link, 'home')
    away_data, away_tooltip_data, away_style_data = team_odds_tab(match_link, 'away')
    return home_data, away_data, home_tooltip_data, away_tooltip_data, home_style_data, away_style_data


if __name__ == '__main__':
    app.run_server(debug=False)

