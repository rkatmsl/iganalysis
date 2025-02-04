import tempfile
import time
import yt_dlp as ytdl
import os
from pathlib import Path
import streamlit as st
from phi.agent import Agent
from phi.model.google import Gemini
from phi.tools.duckduckgo import DuckDuckGo
from google.generativeai import upload_file, get_file
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)

# Initialize session state for tracking files and previous URLs
if 'temp_files' not in st.session_state:
    st.session_state.temp_files = []
if 'previous_url' not in st.session_state:
    st.session_state.previous_url = None
if 'previous_playlist_url' not in st.session_state:
    st.session_state.previous_playlist_url = None
if 'instagram_link_results' not in st.session_state:
    st.session_state.instagram_link_results = {}  # Store analysis results per link

# Function to clean up temporary files
def cleanup_temp_files():
    for file_path in st.session_state.temp_files:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            st.warning(f"Error cleaning up file {file_path}: {e}")
    st.session_state.temp_files = []

# Page configuration
st.set_page_config(
    page_title="Multimodal AI Agent - Video Summarizer",
    page_icon="🎥",
    layout="wide"
)

st.title("Phidata Video AI Summarizer Agent 🎥🎤🖬")
st.header("Powered by Gemini 2.0 Flash Exp")

@st.cache_resource
def initialize_agent():
    return Agent(
        name="Video AI Summarizer",
        model=Gemini(id="gemini-2.0-flash-exp"),
        tools=[DuckDuckGo()],
        markdown=True,
    )

# Initialize the agent
multimodal_Agent = initialize_agent()

# Option to either upload a video, provide a YouTube URL, or provide a YouTube Playlist URL
video_option = st.selectbox(
    "Choose how to provide the video(s) for analysis:",
    options=["Provide Instagram Links"]  # Removed other options for this specific use case
)

# New option to provide Instagram links
if video_option == "Provide Instagram Links":
    instagram_links = st.text_area(
        "Enter Instagram Reel URLs (one per line)",
        placeholder="Paste Instagram Reel links here, one URL per line.",
        help="Provide the links to Instagram Reels for AI analysis."
    ).splitlines()

    instagram_links = [link.strip() for link in instagram_links if link.strip()]

    # Store links in session state
    if 'instagram_links' not in st.session_state:
        st.session_state.instagram_links = []

    if instagram_links != st.session_state.instagram_links:
        cleanup_temp_files()
        st.session_state.instagram_links = instagram_links
        st.session_state.instagram_link_results = {}  # Reset results when links change


    if instagram_links:
        video_paths = []  # List to store downloaded video file paths

        with st.spinner("Downloading Instagram Reels..."):
            for url in instagram_links:
                # Create a temporary directory for downloads
                temp_dir = tempfile.mkdtemp()
                video_filename = Path(temp_dir) / "downloaded_video.mp4"
                st.session_state.temp_files.append(str(video_filename))  # Track the file
                st.session_state.temp_files.append(temp_dir)  # Track the directory

                try:
                    ydl_opts = {
                        'format': 'mp4',
                        'outtmpl': str(video_filename),
                        'postprocessors': [{
                            'key': 'FFmpegVideoConvertor',
                            'preferedformat': 'mp4',
                        }],
                        'quiet': True,  # Suppress verbose output
                    }

                    with ytdl.YoutubeDL(ydl_opts) as ydl:
                        try:
                            info_dict = ydl.extract_info(url, download=True)
                        except Exception as e:
                            st.error(f"Error downloading {url}: {e}")
                            continue  # Skip to next URL if download fails

                    if not video_filename.exists():
                        st.error(f"The video from {url} was not downloaded in the expected format.")
                    else:
                        st.video(str(video_filename), format="video/mp4", start_time=0)
                        video_paths.append(str(video_filename))  # Add to list for analysis

                except Exception as e:
                    st.error(f"An error occurred while downloading the video from {url}: {e}")


# Text input for user to ask questions about the video(s)
user_query = st.text_area(
    "What insights are you seeking from the video?",
    placeholder="Ask anything about the video content. The AI agent will analyze and gather additional context if needed.",
    help="Provide specific questions or insights you want from the video."
)

if st.button("🔍 Analyze Video(s)", key="analyze_video_button"):
    if not user_query:
        st.warning("Please enter a question or insight to analyze the video.")
    else:
        try:
            with st.spinner("Processing video(s) and gathering insights..."):

                # Analyze each video
                # Loop through the instagram links and corresponding video paths
                for url, video_path in zip(st.session_state.instagram_links, video_paths): #Corrected Video Path retrieval
                    processed_video = upload_file(video_path)
                    while processed_video.state.name == "PROCESSING":
                        time.sleep(1)
                        processed_video = get_file(processed_video.name)

                    analysis_prompt = (
                        f"""
                        Analyze the uploaded video from the URL: {url} and respond to the following query:
                        {user_query}

                        Provide a detailed, user-friendly response based on the content of the video.
                        Specifically, identify which of the following brands are mentioned and provide the timestamp for each mention:

                        Pandora, Tiffany & Co., BULGARI, Swarovski, Beyond the Vines, Charles and Keith, Burberry, Coach, Louis Vuitton, Chomel, Bottega Veneta, Cartier, DIOR, GUCCI
                        Bengawan Solo, Läderach Swiss Chocolatier, The Cocoa Trees, Candy Empire, TripletS, L’éclair Patisserie, GIFT by Changi Airport
                        Laneige, Sulwhasoo, Kiehl’s Since 1851, Cosmetics & Perfumes by The Shilla, Maison and Margiela
                        Bottles & Bottles, Lotte Duty Free
                        """
                    )

                    # AI agent processing
                    response = multimodal_Agent.run(analysis_prompt, videos=[processed_video])

                    # Store the result linked to the URL
                    st.session_state.instagram_link_results[url] = response.content

            # Display the results for each URL
            st.subheader("Analysis Results")
            for url, result in st.session_state.instagram_link_results.items():
                st.markdown(f"**Analysis for URL: {url}**")
                st.markdown(result)
                st.write("---")  # Separator between results

        except Exception as error:
            st.error(f"An error occurred during analysis: {error}")

# Customize text area height
st.markdown(
    """
    <style>
    .stTextArea textarea {
        height: 100px;
    }
    </style>
    """,
    unsafe_allow_html=True
)