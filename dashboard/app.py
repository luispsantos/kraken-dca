import plotly.graph_objects as go
from dash import Dash, dcc, html
from dash.dependencies import Input, Output
from plotly.subplots import make_subplots

from kraken import get_asset_prices, get_order_history, load_all_pairs

app = Dash(__name__)


def purchases_formatter(row):
    return (
        f"date: {row.date}<br>"
        f"asset price: {row.pair_price}<br>"
        f"volume: {row.volume:.6f}<br>"
        f"price: {row.price}<br>"
        f"fee: {row.fee:.5f}"
    )


def accumulation_formatter(row):
    return (
        f"date: {row.date}<br>"
        # f"asset price: {row.pair_price}<br>"
        f"volume: {row.volume_cumsum:.6f}<br>"
        f"price: {row.price_cumsum}<br>"
        f"fee: {row.fee_cumsum:.5f}"
    )


def profits_formatter(row):
    return (
        f"date: {row.date}<br>"
        f"total spent: {row.total_price_cumsum:.2f}<br>"
        f"valuation: {row.volume_cumsum * row.latest_price:.2f}<br>"
        f"profit: {row.profit:.2f}"
    )


all_pairs = load_all_pairs()
orders = get_order_history()
orders.sort_values("date", inplace=True)

orders["fee_cumsum"] = orders.groupby("pair").fee.cumsum()
orders["volume_cumsum"] = orders.groupby("pair").volume.cumsum()
orders["price_cumsum"] = orders.groupby("pair").price.cumsum()
orders["total_price_cumsum"] = orders.groupby("pair").total_price.cumsum()

asset_prices = get_asset_prices(orders.pair.unique())
orders["latest_price"] = orders.pair.map(asset_prices)

orders["profit"] = (
    orders.volume_cumsum * orders.latest_price - orders.total_price_cumsum
)

orders["purchases_text"] = orders.apply(purchases_formatter, axis="columns")
orders["accumulation_text"] = orders.apply(
    accumulation_formatter, axis="columns"
)
orders["profits_text"] = orders.apply(profits_formatter, axis="columns")

orders_user_counts = orders.user_name.value_counts()
ordered_users = orders_user_counts.index.tolist()


@app.callback(
    Output("dca-graph", "figure"),
    Input("dca-tabs-graph", "value"),
    Input("account-dropdown", "value"),
)
def render_content(tab, account, scatter_plot_mode="lines+markers"):
    # fetch all the orders only from a certain user
    user_orders = orders.query(f'user_name == "{account}"')

    # sort the traded pairs by their total trading volume
    pair_total_spent = user_orders.groupby("pair").price.sum()
    most_spent_pairs = pair_total_spent.sort_values(ascending=False)

    account_pairs = {pair: all_pairs[pair] for pair in most_spent_pairs.index}
    pair_names = list(account_pairs.values())

    fig = make_subplots(
        rows=len(most_spent_pairs), cols=1, subplot_titles=pair_names
    )
    for row_idx, pair in enumerate(account_pairs, start=1):
        pair_df = user_orders.query(f'pair == "{pair}"')

        if tab == "crypto-purchases":
            figtitle = "Crypto purchases over time"
            subplot = go.Scatter(
                x=pair_df.date,
                y=pair_df.pair_price,
                name=pair,
                text=pair_df.purchases_text,
                hoverinfo="text",
                mode=scatter_plot_mode,
            )

        elif tab == "crypto-accumulation":
            figtitle = "Crypto accumulation over time"
            subplot = go.Scatter(
                x=pair_df.date,
                y=pair_df.volume.cumsum(),
                name=pair,
                text=pair_df.accumulation_text,
                hoverinfo="text",
                mode=scatter_plot_mode,
            )

        elif tab == "crypto-profits":
            subplot = go.Scatter(
                x=pair_df.date,
                y=pair_df.profit,
                name=pair,
                text=pair_df.profits_text,
                hoverinfo="text",
                mode=scatter_plot_mode,
            )
            figtitle = "Crypto profits from latest price"

        fig.append_trace(subplot, row=row_idx, col=1)

    fig.update_layout(height=800, width=1600, title_text=figtitle)

    return fig


app.layout = html.Div(
    children=[
        html.H1(children="DCA Insights"),
        html.Div(children="Draw insights from historical DCA purchases"),
        dcc.Dropdown(
            options=ordered_users,
            value=ordered_users[0],
            placeholder="Select an account",
            style={
                "position": "absolute",
                "top": "10px",
                "left": "50%",
                "width": "48%",
            },
            id="account-dropdown",
        ),
        dcc.Tabs(
            id="dca-tabs-graph",
            value="crypto-purchases",
            children=[
                dcc.Tab(label="Crypto purchases", value="crypto-purchases"),
                dcc.Tab(
                    label="Crypto accumulation", value="crypto-accumulation"
                ),
                dcc.Tab(label="Crypto profits", value="crypto-profits"),
            ],
        ),
        dcc.Graph(id="dca-graph"),
    ]
)

if __name__ == "__main__":
    app.run_server(debug=True)
