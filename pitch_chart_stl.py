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

# table check
def ensure_tables():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pitchers (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
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
            risp BOOLEAN,
            result TEXT,
            batter_hand TEXT CHECK (batter_hand IN ('L', 'R'))
        )
    """)
    conn.commit()
    conn.close()

ensure_tables()

# pitchers db
def get_pitchers():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM pitchers ORDER BY name")
    pitchers = [row[0] for row in cur.fetchall()]
    conn.close()
    return pitchers

# session state setup
if 'page' not in st.session_state:
    st.session_state.page = 'pitcher_date'
if 'pitcher' not in st.session_state:
    st.session_state.pitcher = None
if 'game_date' not in st.session_state:
    st.session_state.game_date = datetime.date.today()

# pitch state
if 'pitch_type' not in st.session_state:
    st.session_state.pitch_type = ""
if 'velocity' not in st.session_state:
    st.session_state.velocity = 0
if 'result' not in st.session_state:
    st.session_state.result = ""
if 'risp' not in st.session_state:
    st.session_state.risp = False
if 'ground_ball' not in st.session_state:
    st.session_state.ground_ball = False
if 'swing' not in st.session_state:
    st.session_state.swing = False
if 'batter_hand' not in st.session_state:
    st.session_state.batter_hand = "R"
if 'location' not in st.session_state:
    st.session_state.location = "MMiddle"

st.title("Pitch Chart")

# page 1
if st.session_state.page == 'pitcher_date':
    st.header("Select Pitcher and Date")

    pitchers = get_pitchers()
    pitcher = st.selectbox("Select Pitcher", options=[""] + pitchers)
    game_date = st.date_input("Game Date", value=st.session_state.game_date)

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
            pitch_type = st.selectbox("Pitch Type", [""] + ["FF", "FT", "CH", "CU", "SL", "SP"], index=0)
            velocity = st.number_input("Velocity", min_value=0, max_value=120, step=1, value=None)
            inning = st.selectbox("Inning", list(range(1, 10)))  # ✅ NEW LINE
            result = st.selectbox("Result", [""] + ["Ball", "Strike", "Foul Ball", "Strikeout", "Walk", "Out", "1B", "2B", "3B", "HR", "Reach On Error", "HBP", "Fielder's Choice"], index=0)

        with col2:
            batter_hand = st.radio("Batter Handedness", ["L", "R"], horizontal=True)
            location = st.selectbox("Location in Strike Zone", ["ULeft", "UMiddle", "URight","MLeft", "MMiddle", "MRight", "LLeft", "LMiddle", "LRight"])
            swing = st.checkbox("Swing?")
            ground_ball = st.checkbox("Ground Ball?")
            risp = st.checkbox("RISP")


        submitted = st.form_submit_button("Submit Pitch")

        if submitted:
            if not pitch_type:
                st.warning("Please select a pitch type.")
            else:
                try:
                    conn = get_connection()
                    cur = conn.cursor()
                    cur.execute("""
                        INSERT INTO pitches (pitcher, date, pitch_type, velocity, inning, swing, ground_ball, risp, result, batter_hand, location)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        st.session_state.pitcher,
                        st.session_state.game_date,
                        pitch_type,
                        velocity if velocity > 0 else None,
                        inning,
                        swing,
                        ground_ball,
                        risp,
                        result if result != "" else None,
                        batter_hand,
                        location
                        
                    ))
                    conn.commit()
                    conn.close()
                    st.success("Pitch saved!")

                    # Reset inputs
                    st.session_state.pitch_type = ""
                    st.session_state.velocity = 0
                    st.session_state.result = ""
                    st.session_state.ground_ball = False
                    st.session_state.swing = False
                    st.session_state.risp = False
                    st.session_state.batter_hand = "R"
                    st.rerun()

                except Exception as e:
                    st.error(f"Error saving pitch: {e}")

    # pitch table
    try:
        conn = get_connection()
        df = pd.read_sql("""
            SELECT id, inning, pitch_type, velocity, batter_hand, swing, ground_ball, risp, result, location
            FROM pitches 
            WHERE pitcher = %s AND date = %s
            ORDER BY id ASC
        """, conn, params=(st.session_state.pitcher, st.session_state.game_date))
        conn.close()

        if df.empty:
            st.info("No pitches entered for this game yet.")
        else:
            df["Pitch #"] = range(1, len(df) + 1)
            df = df[["Pitch #", "inning", "pitch_type", "velocity", "batter_hand", "location", "swing", "ground_ball", "risp", "result"]]
            st.dataframe(
                df.reset_index(drop=True),
                use_container_width=True,
                hide_index=True
            )

    except Exception as e:
        st.error(f"Error loading pitches: {e}")

    if st.button("Back to Pitcher & Date"):
        st.session_state.page = 'pitcher_date'
        st.rerun()
