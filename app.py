import re
import json
import logging
import pandas as pd
import datetime as dt
from sqlalchemy import create_engine

import dash
import dash_auth
import dash_table
from dash.dependencies import Input, Output
import dash_core_components as dcc
import dash_html_components as html
from dash_table.Format import Format


with open('./valid_users.json') as handle:
    VALID_USERNAME_PASSWORD_PAIRS  = json.loads(handle.read())

ENGINE = create_engine('postgresql://' + VALID_USERNAME_PASSWORD_PAIRS['postgresql'])

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
            return '🎄' + odds
            
        elif float(open_odds) > float(odds):
            return '🔻' + odds
        else:
            return odds
    except ValueError:
        return odds


def league_odds_tab(country, league):
    df = DATA.query(f"country=='{country}' and league=='{league}' and finished==False").sort_values('match_dt')
    df = df.reset_index()
    # embed match link in match date
    df['match_dt'] = '**[' + df['match_dt'].dt.strftime('%d.%m.%Y') + '](' + df['match_link'] + ')**'

    # conver odds to float with 2 decimal
    odds_cols = ['home_odds','draw_odds', 'away_odds']
    df[odds_cols] = df[odds_cols].applymap(odds_2_decimal)
    
    # add odds change direction symbol
    df['home_odds'] = df.apply(lambda row: odds_change_direction(row['home_odds'], row['home_open_odds']), axis=1)
    df['draw_odds'] = df.apply(lambda row: odds_change_direction(row['draw_odds'], row['draw_open_odds']), axis=1)
    df['away_odds'] = df.apply(lambda row: odds_change_direction(row['away_odds'], row['away_open_odds']), axis=1)
    
    cols = ['match_dt','home_name', 'away_name', 'home_odds', 'draw_odds', 'away_odds', 'total', 'handicap']
    tooltip_data = []
    style_data_conditional = []
    for row_ix in df.index:
        tooltip_data.append(
            {f'{side}_odds': str(df.loc[row_ix, f'{side}_open_odds']) for side in ['home', 'draw', 'away']}
        )
        
        for col in cols:
            padding = '2px 4px'
            font_size = 15
            font_weight = 'normal'
            bg_color = stripe_rows(row_ix) # stripe tab rows

            if col == 'home_name' or col == 'away_name':
                font_weight = 'bold'
            if col == 'total' or col == 'handicap':
                padding = '2px 12px'
                font_size = 14
            
            style_data_conditional.append(
                {
                    'if': {"row_index": row_ix, 'column_id': col},
                    'backgroundColor': bg_color,
                    'padding': padding,
                    'fontSize': font_size,
                    'fontWeight': font_weight,
                }
            )

    return df[cols].to_dict('records'), tooltip_data, style_data_conditional


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
            'draw_odds', 'away_odds', 'total']
    tooltip_data = []
    style_data_conditional = []
    for row_ix, row in df.iterrows():
        tooltip = {f'{side}_odds': str(df.loc[row_ix, f'{side}_open_odds']) for side in ['home', 'draw', 'away']}
        tooltip['home_odds'] = tooltip['home_odds'] + ' | ' + str(row['handicap'])
        tooltip_data.append(tooltip)
        
        for col in cols:
            color = 'rgb(0, 0, 0)'
            padding = '1px 1px'
            font_size = 14
            font_weight = 'normal'

            if col == 'home_name' and row['home_id'] == team_id:
                font_weight = 'bold'
            elif col == 'away_name' and row['away_id'] == team_id:
                font_weight = 'bold'

            if col == 'league':
                font_size = 13

            if col == 'final_score':
                font_size = 15
                font_weight = 'bold'
                padding = '1px 3px'

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
                padding = '1px 3px'
                if row['match_outcome'] == 'away':
                    bg_color = 'rgb(255, 255, 204)'
                if not row['pinnacle']:
                    color = 'rgb(192, 192, 192)'

            # color result column
            if col == 'result' and row['match_outcome']:
                padding = '1px 3px'
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


def create_h2h_tab(match_link):
    teams_ids = DATA.query(f"match_link == '{match_link}'")[['home_id', 'away_id']].iloc[0].values.tolist()
    h2h = DATA[(DATA['home_id'].isin(teams_ids)) & (DATA['away_id'].isin(teams_ids)) & (DATA['home_odds'] > 0)]
    h2h = h2h.sort_values('match_dt', ascending=False)
    df = h2h.append(pd.Series(), ignore_index=True)

    teams_matches = DATA[(DATA['home_id'].isin(teams_ids)) | (DATA['away_id'].isin(teams_ids))]
    teams_matches = teams_matches[teams_matches['home_odds'] > 0]
    teams_matches = teams_matches.sort_values('match_dt', ascending=False)

    checked_rivals = teams_ids.copy()
    for _, row in teams_matches.iterrows():
        rival_id = row['home_id'] if row['home_id'] not in teams_ids else row['away_id']
        if rival_id in checked_rivals:
            continue
        checked_rivals.append(rival_id)
        matches_with_home = teams_matches[
            teams_matches['home_id'].isin([teams_ids[0], rival_id]) & teams_matches['away_id'].isin([teams_ids[0], rival_id])
        ]
        matches_with_away = teams_matches[
            teams_matches['home_id'].isin([teams_ids[1], rival_id]) & teams_matches['away_id'].isin([teams_ids[1], rival_id])
        ]
        if len(matches_with_home) > 0 and len(matches_with_away) > 0:
            tmp_df = matches_with_home.append(matches_with_away).sort_values('match_dt', ascending=False)
            tmp_df = tmp_df.head(4)
            tmp_df = tmp_df.append(pd.Series(), ignore_index=True)
            df = df.append(tmp_df)

    df = df.reset_index()
    notna_ixs = df[~df['match_link'].isna()].index
    df = df.fillna('')
    # embed match link in match date
    df.loc[notna_ixs, 'match_dt'] = '**[' + df.loc[notna_ixs, 'match_dt'].dt.strftime('%d.%m.%Y') + '](' + df.loc[notna_ixs, 'match_link'] + ')**'

    df.loc[notna_ixs, 'match_outcome'] = df.loc[notna_ixs, 'final_score'].apply(get_outcome)
    df['result'] = '' # empty col to color cell according to match result  win, draw, loss | green, yellow, red

    # conver odds to float with 2 decimal
    odds_cols = ['home_odds','draw_odds', 'away_odds']
    df.loc[notna_ixs, odds_cols] = df.loc[notna_ixs, odds_cols].applymap(odds_2_decimal)
    
    # add odds change direction symbol
    df.loc[notna_ixs, 'home_odds'] = df.loc[notna_ixs].apply(lambda row: odds_change_direction(row['home_odds'], row['home_open_odds']), axis=1)
    df.loc[notna_ixs, 'draw_odds'] = df.loc[notna_ixs].apply(lambda row: odds_change_direction(row['draw_odds'], row['draw_open_odds']), axis=1)
    df.loc[notna_ixs, 'away_odds'] = df.loc[notna_ixs].apply(lambda row: odds_change_direction(row['away_odds'], row['away_open_odds']), axis=1)

    cols = ['match_dt', 'final_score', 'home_name', 'away_name', 'league', 'home_odds',
            'draw_odds', 'away_odds', 'total']
    tooltip_data = []
    style_data_conditional = []
    for row_ix, row in df.iterrows():
        if not row['match_link']:
            tooltip_data.append(
                {f'{side}_odds': None for side in ['home', 'draw', 'away']}
            )
            continue

        tooltip = {f'{side}_odds': str(df.loc[row_ix, f'{side}_open_odds']) for side in ['home', 'draw', 'away']}
        tooltip['home_odds'] = tooltip['home_odds'] + ' | ' + str(row['handicap'])
        tooltip_data.append(tooltip)

        for col in cols:
            color = 'rgb(0, 0, 0)'
            padding = '1px 1px'
            font_size = 14
            font_weight = 'normal'

            if col == 'home_name' and row['home_id'] in teams_ids:
                font_weight = 'bold'
            elif col == 'away_name' and row['away_id'] in teams_ids:
                font_weight = 'bold'

            if col == 'league':
                font_size = 13

            if col == 'final_score':
                font_size = 15
                font_weight = 'bold'
                padding = '1px 3px'

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
                padding = '1px 3px'
                if row['match_outcome'] == 'away':
                    bg_color = 'rgb(255, 255, 204)'
                if not row['pinnacle']:
                    color = 'rgb(192, 192, 192)'
            
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


def create_league_odds_tab(country, league):
    league_data, league_tooltip_data, league_style_data = league_odds_tab(country, league)
    result = html.Div([
        dash_table.DataTable(
            id='table-league',
            columns=[
                {'name': 'Home', 'id': 'home_name'},
                {'name': 'Away', 'id': 'away_name'},
                {'name': 'Date', 'id': 'match_dt', 'presentation':'markdown'},
                {'name': 'Home Odds', 'id': 'home_odds'},
                {'name': 'Draw Odds', 'id': 'draw_odds'},
                {'name': 'Away Odds', 'id': 'away_odds'},
                {'name': 'AH', 'id': 'handicap'},
                {'name': 'O/U', 'id': 'total'}
            ],
            data=league_data,
            tooltip_data=league_tooltip_data,
            style_cell={'height': '20px', 'textAlign': 'center', 'fontWeight': 'normal',
                        'textOverflow': 'ellipsis', 'fontFamily': 'Open Sans'},
            style_data_conditional=league_style_data,
            style_header = {'display': 'none'},
            style_as_list_view = True
        )
    ], className= 'six columns', style={'marginLeft': 450})
    return result


def create_match_tabs(match_link):
    home_data, home_tooltip_data, home_style_data = team_odds_tab(match_link, 'home')
    away_data, away_tooltip_data, away_style_data = team_odds_tab(match_link, 'away')

    home_tab = html.Div([
        dash_table.DataTable(
            id='table-home-side',
            columns=[
                {'name': ' ', 'id': 'result'},
                {'name': 'League', 'id': 'league'},
                {'name': 'Home', 'id': 'home_name'},
                {'name': 'Away', 'id': 'away_name'},
                {'name': 'Date', 'id': 'match_dt', 'presentation':'markdown'},
                {'name': 'Score', 'id': 'final_score'},
                {'name': 'Home Odds', 'id': 'home_odds'},
                {'name': 'Draw Odds', 'id': 'draw_odds'},
                {'name': 'Away Odds', 'id': 'away_odds'},
                {'name': 'O/U', 'id': 'total'}
            ],
            data=home_data,
            tooltip_data=home_tooltip_data,
            style_cell={'height': '20px', 'textAlign': 'center',
                        'textOverflow': 'ellipsis', 'fontFamily': 'Open Sans'},
            style_data_conditional=home_style_data,
            style_header = {'display': 'none'},
            style_as_list_view = True
        )
    ], className= 'four columns', style={'marginLeft': 12})

    away_tab = html.Div([
        dash_table.DataTable(
            id='table-away-side',
            columns=[
                {'name': ' ', 'id': 'result'},
                {'name': 'League', 'id': 'league'},
                {'name': 'Home', 'id': 'home_name'},
                {'name': 'Away', 'id': 'away_name'},
                {'name': 'Date', 'id': 'match_dt', 'presentation':'markdown'},
                {'name': 'Score', 'id': 'final_score'},
                {'name': 'Home Odds', 'id': 'home_odds'},
                {'name': 'Draw Odds', 'id': 'draw_odds'},
                {'name': 'Away Odds', 'id': 'away_odds'},
                {'name': 'O/U', 'id': 'total'}
            ],
            data=away_data,
            tooltip_data=away_tooltip_data,
            style_cell={'height': '20px', 'textAlign': 'center',
                        'textOverflow': 'ellipsis', 'fontFamily': 'Open Sans'},
            style_data_conditional=away_style_data,
            style_header = {'display': 'none'},
            style_as_list_view = True
        )
    ], className= 'four columns', style={'marginLeft': 40})

    h2h_data, h2h_tooltip_data, h2h_style_data = create_h2h_tab(match_link)

    h2h_tab = html.Div([
        dash_table.DataTable(
            id='table-h2h',
            columns=[
                {'name': 'League', 'id': 'league'},
                {'name': 'Home', 'id': 'home_name'},
                {'name': 'Away', 'id': 'away_name'},
                {'name': 'Date', 'id': 'match_dt', 'presentation':'markdown'},
                {'name': 'Score', 'id': 'final_score'},
                {'name': 'Home Odds', 'id': 'home_odds'},
                {'name': 'Draw Odds', 'id': 'draw_odds'},
                {'name': 'Away Odds', 'id': 'away_odds'},
                {'name': 'O/U', 'id': 'total'}
            ],
            data=h2h_data,
            tooltip_data=h2h_tooltip_data,
            style_cell={'height': '20px', 'textAlign': 'center',
                        'textOverflow': 'ellipsis', 'fontFamily': 'Open Sans'},
            style_data_conditional=h2h_style_data,
            style_header = {'display': 'none'},
            style_as_list_view = True
        )
    ], className= 'three columns', style={'marginLeft': 50})

    result = [home_tab, away_tab, h2h_tab]
    return result


def serve_layout():
    layout = html.Div([
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

        # odds table
        html.Div(
            id='odds-table',
            className="row 2",
            style={'marginTop': 30, 'marginBottom': 15}),
    ])    
    return layout


external_stylesheets = [
    'https://codepen.io/chriddyp/pen/bWLwgP.css',
    'https://codepen.io/amyoshino/pen/jzXypZ.css'  # Boostrap CSS
]

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

app.config.suppress_callback_exceptions = True

auth = dash_auth.BasicAuth(
    app,
    VALID_USERNAME_PASSWORD_PAIRS
)

app.layout = serve_layout()


@app.callback(
    Output('countries-dropdown', 'options'),
    [Input('countries-button', 'value')])
def update_country_list(country_button):
    if country_button == 'top':
        countries = sorted(DATA[DATA['country'].isin(TOP_COUNTRIES)]['country'].unique())
    else:
        countries = sorted(DATA['country'].unique())
    values = [{'label':i.capitalize(), 'value':i} for i in countries]
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
    values = [{'label': 'All matches', 'value': None}] + values
    return values


@app.callback(
    Output('odds-table', 'children'),
    [Input('matches-dropdown', 'value'), Input('countries-dropdown', 'value'), Input('leagues-dropdown', 'value')])
def update_odds_tab(match_link, country, league):
    if match_link:
        return create_match_tabs(match_link)
    return create_league_odds_tab(country, league)


if __name__ == '__main__':
    logging.basicConfig(
    filename='./oddstab.log',
    filemode='a',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
    logger = logging.getLogger(__name__)

    app.run_server(debug=False)
