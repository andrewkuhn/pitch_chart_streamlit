import streamlit as st
import psycopg2
import pandas as pd
import datetime
import os

# db setup
def get_db_params():
    return {
        "dbname": st.secrets["DB_NAME"],
        "user": st.secrets["DB_USER"],
        "password": st.secrets["DB_PASSWORD"],
        "host": st.secrets["DB_HOST"],
        "port": st.secrets["DB_PORT"],
    }

def get_connection():
    params = get_db_params()
    return psycopg2.connect(**params)

def ensure_tables():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pitchers (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            handedness TEXT CHECK (handedness IN ('L', 'R')) NOT NULL DEFAULT 'R'
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pitches (
            id SERIAL PRIMARY KEY,
            pitcher TEXT NOT NULL,
            date DATE NOT NULL,
            pitch_type TEXT,
            velocity INTEGER,
            swing BOOLEAN,
            ground_ball BOOLEAN,
            result TEXT
        )
    """)
    conn.commit()
    conn.close()

ensure_tables()

def get_pitchers():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM pitchers ORDER BY name")
    pitchers = [row[0] for row in cur.fetchall()]
    conn.close()
    return pitchers

def get_pitcher_handedness(name):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT handedness FROM pitchers WHERE name = %s", (name,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else None

def add_pitcher(name, handedness):
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO pitchers (name, handedness)
            VALUES (%s, %s)
            ON CONFLICT (name) DO NOTHING
        """, (name, handedness))
        conn.commit()
    finally:
        conn.close()

# session state setup
if 'page' not in st.session_state:
    st.session_state.page = 'pitcher_date'
if 'pitcher' not in st.session_state:
    st.session_state.pitcher = None
if 'game_date' not in st.session_state:
    # Set to Eastern time
    from pytz import timezone
    eastern = timezone('US/Eastern')
    today_eastern = datetime.datetime.now(eastern).date()
    st.session_state.game_date = today_eastern

# pitch state
for key in ['pitch_type', 'velocity', 'result', 'ground_ball', 'swing']:
    if key not in st.session_state:
        st.session_state[key] = "" if key in ['pitch_type', 'result'] else False if key in ['ground_ball', 'swing'] else 0

st.title("Pitch Chart")

# page 1
if st.session_state.page == 'pitcher_date':
    st.header("Select Pitcher and Date")

    pitchers = get_pitchers()
    pitcher = st.selectbox("Select Pitcher", options=[""] + pitchers)
    game_date = st.date_input("Game Date", value=st.session_state.game_date)

    if pitcher:
        handedness = get_pitcher_handedness(pitcher)
        if handedness:
            st.markdown(f"**Handedness:** {handedness}")
    else:
        st.subheader("Add New Pitcher")
        new_pitcher_name = st.text_input("Pitcher Name")
        new_pitcher_hand = st.radio("Handedness", ["L", "R"], horizontal=True)
        if st.button("Add Pitcher"):
            if new_pitcher_name:
                add_pitcher(new_pitcher_name, new_pitcher_hand)
                st.success(f"Pitcher {new_pitcher_name} added.")
                st.rerun()
            else:
                st.warning("Please enter a name for the new pitcher.")

    if st.button("Continue"):
        if not pitcher:
            st.warning("Please select a pitcher.")
        else:
            st.session_state.pitcher = pitcher
            st.session_state.game_date = game_date
            st.session_state.page = 'pitch_entry'
            st.rerun()

# page 2
elif st.session_state.page == 'pitch_entry':
    st.header(f"Pitch Entry for {st.session_state.pitcher} on {st.session_state.game_date}")

    with st.form("pitch_form"):
        col1, col2 = st.columns(2)

        with col1:
            pitch_type = st.selectbox("Pitch Type", [""] + ["FF", "2S", "CH", "CU", "SL", "SP"], index=0)
            velocity = st.number_input("Velocity", min_value=0, max_value=120, step=1, value=None)
            result = st.selectbox("Result", [""] + ["Ball", "Strike", "Foul Ball", "Out", "1B", "2B", "3B", "HR"], index=0)

        with col2:
            ground_ball = st.checkbox("Ground Ball?")
            swing = st.checkbox("Swing?")

        submitted = st.form_submit_button("Submit Pitch")

        if submitted:
            if not pitch_type:
                st.warning("Please select a pitch type.")
            else:
                try:
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO pitches (pitcher, date, pitch_type, velocity, swing, ground_ball, result)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        st.session_state.pitcher,
                        st.session_state.game_date,
                        pitch_type,
                        velocity if velocity > 0 else None,
                        swing,
                        ground_ball,
                        result if result != "" else None
                    ))
                    conn.commit()
                    conn.close()
                    st.success("Pitch saved!")

                    for key in ['pitch_type', 'velocity', 'result', 'ground_ball', 'swing']:
                        st.session_state[key] = "" if key in ['pitch_type', 'result'] else False if key in ['ground_ball', 'swing'] else 0

                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving pitch: {e}")

    # pitches table
    try:
        conn = get_connection()
        df = pd.read_sql("""
            SELECT id, pitch_type, velocity, swing, ground_ball, result
            FROM pitches
            WHERE pitcher = %s AND date = %s
            ORDER BY id ASC
        """, conn, params=(st.session_state.pitcher, st.session_state.game_date))
        conn.close()

        if df.empty:
            st.info("No pitches entered for this game yet.")
        else:
            df["Pitch #"] = range(1, len(df) + 1)
            df = df[["Pitch #", "pitch_type", "velocity", "swing", "ground_ball", "result"]]
            st.dataframe(df, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"Error loading pitches: {e}")

    if st.button("Back to Pitcher & Date"):
        st.session_state.page = 'pitcher_date'
        st.rerun()
