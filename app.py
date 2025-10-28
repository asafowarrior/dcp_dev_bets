import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go

# Set page configuration for wider layout
st.set_page_config(
    page_title="Betting Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Download data from Supabase with pagination and duplicate handling
@st.cache_data
def load_data(table_name):
    # Use Streamlit secrets for API keys
    headers = {
        "apikey": st.secrets["SUPABASE_KEY"],
        "Authorization": f"Bearer {st.secrets['SUPABASE_KEY']}"
    }
    
    all_data = []
    page = 0
    limit = 1000
    
    while True:
        start = page * limit
        
        response = requests.get(
            f"https://xbzzjcurduwqxhpyspom.supabase.co/rest/v1/{table_name}?select=*",
            headers=headers,
            params={
                "limit": limit,
                "offset": start
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if not data:
                break
            all_data.extend(data)
            page += 1
            
            if len(data) < limit:
                break
        else:
            st.error(f"Error loading data from {table_name}: {response.status_code}")
            break
    
    if all_data:
        df = pd.DataFrame(all_data)
        
        # FIXED: Better date conversion with error handling
        date_cols = ['start_time', 'bet_logged', 'created_at']
        for col in date_cols:
            if col in df.columns:
                try:
                    # Convert to datetime, coerce errors to NaT
                    df[col] = pd.to_datetime(df[col], errors='coerce', utc=True)
                    
                    # Log conversion results
                    null_count = df[col].isnull().sum()
                    if null_count > 0:
                        st.sidebar.warning(f"⚠️ {null_count} {col} values could not be converted to datetime in {table_name}")
                    
                except Exception as e:
                    st.sidebar.error(f"❌ Error converting {col} in {table_name}: {e}")
                    # Keep original column if conversion fails
        
        # Remove duplicate bets across bookmakers
        original_count = len(df)
        
        if table_name == "ev_daily_bets":
            # For ev_daily_bets, keep only one record per unique bet combination
            unique_cols = ['event', 'start_time', 'outcome', 'stake', 'odds']
            if all(col in df.columns for col in unique_cols):
                df = df.drop_duplicates(subset=unique_cols, keep='first')
        
        # Remove duplicate IDs if they exist
        if 'id' in df.columns:
            df = df.drop_duplicates(subset=['id'], keep='first')
        
        removed_count = original_count - len(df)
        if removed_count > 0:
            st.sidebar.warning(f"⚠️ Removed {removed_count} duplicate bets from {table_name}")
        
        st.sidebar.success(f"✅ Cleaned data: {len(df)} records from {table_name}")
        return df
    return None

def remove_duplicate_bets(df, table_name):
    """Remove duplicate bets that are the same across multiple bookmakers"""
    original_count = len(df)
    
    if table_name == "ev_daily_bets":
        unique_cols = ['event', 'start_time', 'outcome', 'stake', 'odds']
        if all(col in df.columns for col in unique_cols):
            df = df.drop_duplicates(subset=unique_cols, keep='first')
    
    st.sidebar.info(f"Filtered to {len(df)} unique bets (removed {original_count - len(df)} duplicates)")
    return df

# Dashboard title
st.title("📊 DCP Betting Analytics Dashboard")

# Table selector
st.sidebar.header("🔧 Data Source")
table_option = st.sidebar.radio(
    "Choose data to display:",
    ["betting_analytics", "ev_daily_bets", "matched_betting_bets", "All Tables"],
    help="Select which dataset to analyze",
    index=3  # "All Tables" is the 4th item (index 3)
)

# Duplicate handling option
st.sidebar.header("🎯 Analysis Options")
duplicate_handling = st.sidebar.radio(
    "Handle same bets on multiple bookmakers:",
    ["Keep all bookmakers", "Keep first occurrence only"],
    index=0  # Optional: set default for this radio button too
)

# Load selected data
if table_option == "All Tables":
    df1 = load_data("betting_analytics")
    df2 = load_data("ev_daily_bets")
    df3 = load_data("matched_betting_bets")
    
    if df1 is not None and df2 is not None and df3 is not None:
        # Add source identifier
        df1['data_source'] = 'betting_analytics'
        df2['data_source'] = 'ev_daily_bets'
        df3['data_source'] = 'matched_betting_bets'
        
        # Apply duplicate handling if selected
        if duplicate_handling == "Keep first occurrence only":
            df2 = remove_duplicate_bets(df2, 'ev_daily_bets')
        
        # Combine data
        df_combined = pd.concat([df1, df2, df3], ignore_index=True)
        df = df_combined
    else:
        st.error("Failed to load one or more tables from Supabase")
        st.stop()
else:
    df = load_data(table_option)
    if df is None:
        st.error(f"Failed to load data from {table_option} table")
        st.stop()
    
    # Apply duplicate handling if selected
    if duplicate_handling == "Keep first occurrence only" and table_option == "ev_daily_bets":
        df = remove_duplicate_bets(df, 'ev_daily_bets')

# Display data source info
if table_option == "All Tables":
    st.info(f"📁 Displaying combined data: {len(df1)} records from betting_analytics + {len(df2)} records from ev_daily_bets + {len(df3)} records from matched_betting_bets = {len(df)} total records")
else:
    st.info(f"📁 Displaying data from: **{table_option}** table ({len(df)} records)")

# Date debug info in sidebar - FIXED TIMEZONE ISSUE
st.sidebar.header("📅 Date Info")
available_date_cols = [col for col in ['bet_logged', 'created_at', 'start_time'] if col in df.columns]
st.sidebar.write(f"Available date columns: {available_date_cols}")

# Check for future dates in the best available column - FIXED TIMEZONE HANDLING
if 'bet_logged' in df.columns:
    date_col_to_check = 'bet_logged'
elif 'created_at' in df.columns:
    date_col_to_check = 'created_at'
else:
    date_col_to_check = 'start_time'

if date_col_to_check in df.columns:
    # FIXED: Safe timezone check
    current_time = pd.Timestamp.now(tz='UTC')
    
    # Check if the column is datetime type before accessing .dt
    if pd.api.types.is_datetime64_any_dtype(df[date_col_to_check]):
        if df[date_col_to_check].dt.tz is None:
            # Timezone-naive - convert to naive for comparison
            current_time = current_time.tz_localize(None)
    
    future_records = df[df[date_col_to_check] > current_time]
    if len(future_records) > 0:
        st.sidebar.warning(f"Found {len(future_records)} future {date_col_to_check} dates")
        st.sidebar.write(f"Future range: {future_records[date_col_to_check].min().strftime('%Y-%m-%d')}")

# Key metrics - using columns for better layout
st.header("📈 Key Performance Indicators")

# First row of metrics
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("Total Bets", f"{len(df):,}")
with col2:
    total_profit = df['profit'].sum()
    st.metric("Total Profit", f"R{total_profit:,.2f}")
with col3:
    if 'ev' in df.columns:
        avg_ev = df['ev'].mean()
    elif 'logged_ev' in df.columns:
        avg_ev = df['logged_ev'].mean()
    else:
        avg_ev = 0
    st.metric("Avg EV", f"{avg_ev:.1f}%")
with col4:
    win_rate = (df['profit'] > 0).mean()
    st.metric("Win Rate", f"{win_rate:.1%}")
with col5:
    if 'stake' in df.columns and df['stake'].sum() > 0:
        combined_yield = (total_profit / df['stake'].sum()) * 100
        st.metric("Combined Yield", f"{combined_yield:.1f}%")
    else:
        st.metric("Combined Yield", "N/A")

# Additional metrics if showing all tables
if table_option == "All Tables":
    st.subheader("📊 Table Breakdown")
    col6, col7, col8, col9, col10 = st.columns(5)
    
    with col6:
        st.metric("betting_analytics Bets", f"{len(df1):,}")
    with col7:
        st.metric("ev_daily_bets Bets", f"{len(df2):,}")
    with col8:
        st.metric("matched_betting_bets Bets", f"{len(df3):,}")
    with col9:
        avg_stake = df['stake'].mean() if 'stake' in df.columns else 0
        st.metric("Avg Stake", f"R{avg_stake:.2f}")
    with col10:
        total_stake = df['stake'].sum() if 'stake' in df.columns else 0
        st.metric("Total Stake", f"R{total_stake:,.2f}")

# Create tabs for better organization in wide layout
tab1, tab2, tab3, tab4 = st.tabs(["📈 Performance Charts", "🎯 Bet Analysis", "📅 Time Series", "📋 Raw Data"])

with tab1:
    # Create two columns for charts
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        # 1. Yield by Bookmaker
        if 'bookmaker' in df.columns and 'stake' in df.columns:
            st.subheader("📈 Yield by Bookmaker")
            bookmaker_yield = df.groupby('bookmaker').agg({
                'profit': 'sum',
                'stake': 'sum'
            }).reset_index()
            bookmaker_yield['yield'] = (bookmaker_yield['profit'] / bookmaker_yield['stake']) * 100

            fig1 = px.bar(bookmaker_yield, x='bookmaker', y='yield', 
                          title=f"Yield % by Bookmaker",
                          color='yield',
                          color_continuous_scale='RdYlGn')
            st.plotly_chart(fig1, use_container_width=True)
    
    with col_chart2:
        # 2. Profit by Odds Range
        if 'odds' in df.columns:
            st.subheader("🎯 Profit by Odds Range")
            df['odds_bin'] = pd.cut(df['odds'], bins=[0, 1.5, 2, 3, 5, 10, 100], 
                                    labels=['1-1.5', '1.5-2', '2-3', '3-5', '5-10', '10+'])
            odds_profit = df.groupby('odds_bin')['profit'].sum().reset_index()

            fig2 = px.bar(odds_profit, x='odds_bin', y='profit', 
                          title=f"Total Profit by Odds Range",
                          color='profit',
                          color_continuous_scale='RdYlGn')
            st.plotly_chart(fig2, use_container_width=True)

    # Performance by Data Source (only when all tables are selected)
    if table_option == "All Tables":
        st.subheader("🔄 Comparison: All Tables")
        
        # Create two columns for comparison charts
        col_comp1, col_comp2 = st.columns(2)
        
        with col_comp1:
            # Yield by data source
            source_yield = df.groupby('data_source').agg({
                'profit': 'sum',
                'stake': 'sum'
            }).reset_index()
            source_yield['yield'] = (source_yield['profit'] / source_yield['stake']) * 100
            
            fig_comparison = px.bar(source_yield, x='data_source', y='yield',
                                   title="Yield Comparison Between Tables",
                                   color='data_source')
            st.plotly_chart(fig_comparison, use_container_width=True)
        
        with col_comp2:
            # Profit by data source
            source_profit = df.groupby('data_source')['profit'].sum().reset_index()
            fig_profit = px.pie(source_profit, values='profit', names='data_source',
                               title="Profit Distribution by Table")
            st.plotly_chart(fig_profit, use_container_width=True)

with tab2:
    # Bet Analysis Tab
    st.subheader("🔍 Detailed Bet Analysis")
    
    col_analysis1, col_analysis2 = st.columns(2)
    
    with col_analysis1:
        # Sport analysis
        if 'sport' in df.columns:
            sport_profit = df.groupby('sport').agg({
                'profit': 'sum',
                'stake': 'sum'
            }).reset_index()
            sport_profit['yield'] = (sport_profit['profit'] / sport_profit['stake']) * 100
            sport_profit = sport_profit.sort_values('profit', ascending=False)
            
            fig_sport = px.bar(sport_profit.head(10), x='sport', y='profit',
                              title="Top 10 Sports by Profit")
            st.plotly_chart(fig_sport, use_container_width=True)
    
    with col_analysis2:
        # Bookmaker profit distribution
        if 'bookmaker' in df.columns:
            bookmaker_profit = df.groupby('bookmaker')['profit'].sum().reset_index()
            bookmaker_profit = bookmaker_profit.sort_values('profit', ascending=False)
            
            fig_bookmaker = px.bar(bookmaker_profit.head(10), x='bookmaker', y='profit',
                                  title="Top 10 Bookmakers by Profit")
            st.plotly_chart(fig_bookmaker, use_container_width=True)

with tab3:
    # Time Series Analysis
    st.subheader("📅 Time Series Analysis")
    
    col_time1, col_time2 = st.columns(2)
    
    with col_time1:
        # Cumulative Profit Over Time - FIXED WITH BETTER ERROR HANDLING
        st.subheader("📈 Cumulative Profit Over Time")
        
        if len(df) > 0:
            # Handle timezone-naive timestamps properly
            current_time = pd.Timestamp.now(tz='UTC')
            
            # Determine which date column to use based on available columns and table type
            if table_option == "matched_betting_bets" or (table_option == "All Tables" and 'start_time' in df.columns):
                # For matched_betting_bets, use start_time (event date)
                date_col = 'start_time'
                date_label = 'Event Date'
            elif 'bet_logged' in df.columns:
                date_col = 'bet_logged'
                date_label = 'Date Bet Was Placed'
            elif 'created_at' in df.columns:
                date_col = 'created_at'
                date_label = 'Date Record Created'
            else:
                date_col = 'start_time'
                date_label = 'Event Start Time'
            
            # FIXED: Safe timezone handling
            if date_col in df.columns and pd.api.types.is_datetime64_any_dtype(df[date_col]):
                if df[date_col].dt.tz is None:
                    # Timezone-naive - convert comparison time
                    comparison_time = current_time.tz_localize(None)
                else:
                    # Timezone-aware - keep as UTC
                    comparison_time = current_time
                
                # Filter out future dates
                df_filtered = df[df[date_col] <= comparison_time].copy()
                
                if len(df_filtered) < len(df):
                    future_count = len(df) - len(df_filtered)
                    st.info(f"Filtered out {future_count} future records to fix timeline")
                
                if len(df_filtered) > 0:
                    # Sort by the chosen date column
                    df_sorted = df_filtered.sort_values(date_col)
                    
                    # Calculate cumulative profit
                    df_sorted['cumulative_profit'] = df_sorted['profit'].cumsum()
                    
                    # Add data source to hover info if we have multiple tables
                    if table_option == "All Tables" and 'data_source' in df_sorted.columns:
                        hover_data = ['data_source']
                        # Show breakdown by source in legend
                        fig_cumulative = px.line(df_sorted, x=date_col, y='cumulative_profit', 
                                               title=f"Cumulative Profit Over Time - {table_option}",
                                               labels={'cumulative_profit': 'Cumulative Profit ($)', date_col: date_label},
                                               color='data_source',
                                               hover_data=hover_data)
                    else:
                        # Single table - just one line
                        fig_cumulative = px.line(df_sorted, x=date_col, y='cumulative_profit', 
                                               title=f"Cumulative Profit Over Time - {table_option}",
                                               labels={'cumulative_profit': 'Cumulative Profit ($)', date_col: date_label})
                    
                    fig_cumulative.add_hline(y=0, line_dash="dash", line_color="red", 
                                           annotation_text="Break-even")
                    
                    # Add styling
                    fig_cumulative.update_traces(line=dict(width=3))
                    fig_cumulative.update_layout(hovermode='x unified')
                    
                    st.plotly_chart(fig_cumulative, use_container_width=True)
                    
                    # Show current profit and date range
                    current_profit = df_sorted['cumulative_profit'].iloc[-1]
                    date_range = f"{df_sorted[date_col].min().strftime('%Y-%m-%d')} to {df_sorted[date_col].max().strftime('%Y-%m-%d')}"
                    
                    col_metric1, col_metric2 = st.columns(2)
                    with col_metric1:
                        st.metric("Current Total Profit", f"${current_profit:,.2f}")
                    with col_metric2:
                        st.metric("Date Range", date_range)
                    
                    # DEBUG: Show profit breakdown by table when viewing "All Tables"
                    if table_option == "All Tables":
                        st.subheader("🔍 Profit Breakdown by Table")
                        profit_by_table = df_sorted.groupby('data_source')['profit'].sum().reset_index()
                        st.dataframe(profit_by_table, use_container_width=True)
                        
                else:
                    st.warning("No data available after filtering future dates")
            else:
                st.warning(f"Date column '{date_col}' is not available or not in datetime format")
        else:
            st.warning("No data available for cumulative profit calculation")
    
    with col_time2:
        # Monthly Profit Chart (for All Tables)
        if table_option == "All Tables":
            monthly_data = []
            
            for source, source_df in [('betting_analytics', df1), ('ev_daily_bets', df2), ('matched_betting_bets', df3)]:
                if 'start_time' in source_df.columns and pd.api.types.is_datetime64_any_dtype(source_df['start_time']) and 'profit' in source_df.columns:
                    source_df['month'] = source_df['start_time'].dt.to_period('M')
                    monthly_profit = source_df.groupby('month')['profit'].sum().reset_index()
                    monthly_profit['data_source'] = source
                    monthly_data.append(monthly_profit)
            
            if monthly_data:
                monthly_df = pd.concat(monthly_data, ignore_index=True)
                monthly_df['month'] = monthly_df['month'].astype(str)
                
                # Create stacked bar chart
                fig_monthly = px.bar(monthly_df, x='month', y='profit', color='data_source',
                                    title="Monthly Profit by Data Source",
                                    labels={'profit': 'Profit ($)', 'month': 'Month'},
                                    barmode='stack')
                st.plotly_chart(fig_monthly, use_container_width=True)

with tab4:
    # Raw Data Tab
    st.subheader("📋 Raw Data")
    
    if table_option == "All Tables":
        raw_tab1, raw_tab2, raw_tab3 = st.tabs(["betting_analytics", "ev_daily_bets", "matched_betting_bets"])
        with raw_tab1:
            st.dataframe(df1, use_container_width=True)
            st.write(f"**Columns:** {list(df1.columns)}")
        with raw_tab2:
            st.dataframe(df2, use_container_width=True)
            st.write(f"**Columns:** {list(df2.columns)}")
        with raw_tab3:
            st.dataframe(df3, use_container_width=True)
            st.write(f"**Columns:** {list(df3.columns)}")
    else:
        st.dataframe(df, use_container_width=True)
        st.write(f"**Columns:** {list(df.columns)}")

# Data summary in sidebar
st.sidebar.header("📊 Data Summary")
st.sidebar.write(f"**Table:** {table_option}")
st.sidebar.write(f"**Total Records:** {len(df):,}")
st.sidebar.write(f"**Total Profit:** ${total_profit:,.2f}")
st.sidebar.write(f"**Win Rate:** {win_rate:.1%}")

if table_option == "All Tables":
    st.sidebar.write("---")
    st.sidebar.write("**Table Comparison:**")
    st.sidebar.write(f"betting_analytics: {len(df1):,} bets")
    st.sidebar.write(f"ev_daily_bets: {len(df2):,} bets")
    st.sidebar.write(f"matched_betting_bets: {len(df3):,} bets")

# Add some custom CSS to maximize space
st.markdown("""
<style>
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)