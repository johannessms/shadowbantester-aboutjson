import streamlit as st
import requests
import time
import pandas as pd
import concurrent.futures
from datetime import datetime
import io
import random
import zipfile

MAX_WORKERS = 5
MAX_RETRIES = 3

# Liste von User-Agents für Rotation
USER_AGENTS = [
    # Chrome (verschiedene Versionen und Plattformen)
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    # Firefox
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7; rv:120.0) Gecko/20100101 Firefox/120.0',
    # Safari
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1',
    # Edge
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    # Opera
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/95.0.0.0',
    # Googlebot
    'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
    # Bingbot
    'Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)',
]

ACCEPT_HEADERS = [
    'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'text/html,application/xml;q=0.9,*/*;q=0.8',
]
ACCEPT_LANGUAGE_HEADERS = [
    'en-US,en;q=0.9',
    'en-GB,en;q=0.8',
    'de-DE,de;q=0.9,en;q=0.8',
]
ACCEPT_ENCODING_HEADERS = [
    'gzip, deflate, br',
    'gzip, deflate',
]
CONNECTION_HEADERS = [
    'keep-alive',
    'close',
]
UPGRADE_INSECURE_REQUESTS_HEADERS = ['1']
SEC_FETCH_DEST_HEADERS = ['document']
SEC_FETCH_MODE_HEADERS = ['navigate']
SEC_FETCH_SITE_HEADERS = ['none']
SEC_FETCH_USER_HEADERS = ['?1']

# Proxy-Handling
def load_proxies():
    try:
        with open("proxies.txt", "r") as f:
            proxies = [line.strip() for line in f if line.strip()]
        return proxies
    except Exception:
        return []

proxies = load_proxies()

def get_proxy(index):
    if proxies:
        proxy_url = proxies[index % len(proxies)]
        return {"http": proxy_url, "https": proxy_url}
    else:
        return None

def get_random_user_agent():
    return random.choice(USER_AGENTS)

# User-Agent Auswahl und Delay-Slider in der UI
st.sidebar.header("Request Settings")
rotate_user_agents = st.sidebar.checkbox("Rotate User-Agent (random)", value=True)
user_agent = st.sidebar.selectbox("Choose User-Agent", USER_AGENTS)
delay = st.sidebar.slider("Delay between requests (seconds)", min_value=0.1, max_value=5.0, value=0.5, step=0.1)

def get_random_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS) if rotate_user_agents else user_agent,
        'Accept': random.choice(ACCEPT_HEADERS),
        'Accept-Language': random.choice(ACCEPT_LANGUAGE_HEADERS),
        'Accept-Encoding': random.choice(ACCEPT_ENCODING_HEADERS),
        'Connection': random.choice(CONNECTION_HEADERS),
        'Upgrade-Insecure-Requests': random.choice(UPGRADE_INSECURE_REQUESTS_HEADERS),
        'Sec-Fetch-Dest': random.choice(SEC_FETCH_DEST_HEADERS),
        'Sec-Fetch-Mode': random.choice(SEC_FETCH_MODE_HEADERS),
        'Sec-Fetch-Site': random.choice(SEC_FETCH_SITE_HEADERS),
        'Sec-Fetch-User': random.choice(SEC_FETCH_USER_HEADERS),
    }

def is_shadowbanned(username, proxy=None, proxy_index=None):
    url = f"https://www.reddit.com/user/{username}/about.json"
    headers = get_random_headers()
    proxy_attempts = 0
    max_proxy_attempts = len(proxies) if proxies else 1
    current_proxy_index = proxy_index if proxy_index is not None else 0
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, headers=headers, timeout=5, proxies=proxy)
            if response.status_code == 404:
                return {
                    "Username": username,
                    "Status": "Shadowbanned or does not exist",
                    "Created": "-",
                    "Post Karma": "-",
                    "Comment Karma": "-"
                }
            elif response.status_code == 200:
                data = response.json()["data"]
                created_utc = datetime.utcfromtimestamp(data["created_utc"]).strftime('%Y-%m-%d')
                post_karma = f"{data.get('link_karma', 0):,}".replace(",", ".")
                comment_karma = f"{data.get('comment_karma', 0):,}".replace(",", ".")
                return {
                    "Username": username,
                    "Status": "Not shadowbanned",
                    "Created": created_utc,
                    "Post Karma": post_karma,
                    "Comment Karma": comment_karma
                }
            elif response.status_code == 429 and proxies:
                # Wechsel zur nächsten Proxy
                proxy_attempts += 1
                if proxy_attempts >= max_proxy_attempts:
                    break
                current_proxy_index = (current_proxy_index + 1) % len(proxies)
                proxy = {"http": proxies[current_proxy_index], "https": proxies[current_proxy_index]}
                continue
            else:
                return {
                    "Username": username,
                    "Status": f"Error: {response.status_code}",
                    "Created": "-",
                    "Post Karma": "-",
                    "Comment Karma": "-"
                }
        except requests.exceptions.Timeout:
            time.sleep(2 * attempt)
        except Exception:
            break
    return {
        "Username": username,
        "Status": "Error during check",
        "Created": "-",
        "Post Karma": "-",
        "Comment Karma": "-"
    }

# Proxy editor UI
with st.expander("Edit proxies (one per line, e.g. http://user:pass@ip:port)"):
    proxy_text = st.text_area("Proxies", value="\n".join(proxies), height=200)
    if st.button("Save proxies"):
        with open("proxies.txt", "w") as f:
            f.write(proxy_text.strip() + "\n")
        st.success("Proxies saved. Please reload the app to use the new proxies.")

if st.button("Test proxies and remove invalid ones"):
    proxies_raw = load_proxies()
    # Remove everything after the first comma (if present)
    proxies_clean = [p.split(",")[0] for p in proxies_raw]
    working, failed = test_proxies(proxies_clean)
    # Write only working proxies back to the file
    with open("proxies.txt", "w") as f:
        for p in working:
            f.write(p + "\n")
    st.write(f"{len(working)} proxies are working, {len(failed)} were removed.")
    if failed:
        st.write("Removed proxies:")
        st.write(failed)

# Verschiebe die Checkbox 'Use proxies' nach unten
use_proxies = st.checkbox("Use proxies", value=True)

def process_batch(usernames, progress_bar, use_proxies=True):
    results = []
    total = len(usernames)
    def worker(username, proxy, proxy_index):
        result = is_shadowbanned(username, proxy, proxy_index)
        time.sleep(delay)  # Verwende das gewählte Delay
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_username = {
            executor.submit(
                worker,
                username,
                get_proxy(i) if use_proxies else None,
                i if use_proxies else None
            ): username
            for i, username in enumerate(usernames)
        }
        for i, future in enumerate(concurrent.futures.as_completed(future_to_username)):
            result = future.result()
            results.append(result)
            progress_bar.progress((i + 1) / total)
    return results

def test_proxies(proxy_list):
    working = []
    failed = []
    test_url = "https://www.reddit.com/"
    headers = {'User-Agent': get_random_user_agent()}  # Zufälliger User-Agent für Proxy-Tests
    for proxy_url in proxy_list:
        proxy = {"http": proxy_url, "https": proxy_url}
        try:
            resp = requests.get(test_url, headers=headers, proxies=proxy, timeout=5)
            if resp.status_code == 200:
                working.append(proxy_url)
            else:
                failed.append(proxy_url)
        except Exception:
            failed.append(proxy_url)
    return working, failed

st.title("Reddit Shadowbantester 1.2")  # Version erhöht wegen User-Agent Update

uploaded_file = st.file_uploader("CSV or Excel with usernames upload", type=["csv", "xlsx"])

usernames = []

if uploaded_file is not None:
    if uploaded_file.name.endswith('.csv'):
        df_upload = pd.read_csv(uploaded_file)
    else:
        df_upload = pd.read_excel(uploaded_file)
    # Versuche, eine Spalte mit dem Namen "Username" zu finden, sonst nimm die erste Spalte
    if "Username" in df_upload.columns:
        usernames = df_upload["Username"].astype(str).tolist()
    else:
        usernames = df_upload.iloc[:, 0].astype(str).tolist()
    # Entferne führendes 'u/' falls vorhanden
    usernames = [u.lstrip().removeprefix('u/').strip() for u in usernames if u.strip()]
    st.success(f"{len(usernames)} Usernamen aus Datei geladen.")
else:
    st.write("Enter multiple Reddit usernames (one per line):")
    usernames_input = st.text_area("Usernames", height=200)
    usernames = [u.lstrip().removeprefix('u/').strip() for u in usernames_input.splitlines() if u.strip()]

if st.button("Check"):
    if not usernames:
        st.warning("Bitte gib mindestens einen Usernamen ein oder lade eine Datei hoch.")
    else:
        progress_bar = st.progress(0)
        results = process_batch(usernames, progress_bar, use_proxies=use_proxies)
        df = pd.DataFrame(results, columns=["Username", "Status", "Created", "Post Karma", "Comment Karma"])
        st.write("**Results:**")
        st.dataframe(df, use_container_width=True)
        # Summary
        banned_count = (df["Status"] == "Shadowbanned or does not exist").sum()
        not_banned_count = (df["Status"] == "Not shadowbanned").sum()
        st.markdown(f"**Summary:** <span style='color:red'>{banned_count} shadowbanned (or do not exist)</span>, <span style='color:green'><b>{not_banned_count} not shadowbanned</b></span>.", unsafe_allow_html=True)

        # Download-Buttons in einem Expander gruppieren
        with st.expander("Downloads"):
            excel_all = io.BytesIO()
            df.to_excel(excel_all, index=False, engine='openpyxl')
            excel_all.seek(0)
            df_shadowbanned = df[df["Status"] == "Shadowbanned or does not exist"]
            excel_shadowbanned = io.BytesIO()
            df_shadowbanned.to_excel(excel_shadowbanned, index=False, engine='openpyxl')
            excel_shadowbanned.seek(0)
            df_not_shadowbanned = df[df["Status"] == "Not shadowbanned"]
            excel_not_shadowbanned = io.BytesIO()
            df_not_shadowbanned.to_excel(excel_not_shadowbanned, index=False, engine='openpyxl')
            excel_not_shadowbanned.seek(0)

            st.download_button(
                label="Download results as Excel",
                data=excel_all,
                file_name=f"shadowban_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.download_button(
                label="Download only shadowbanned as Excel",
                data=excel_shadowbanned,
                file_name=f"shadowbanned_only_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.download_button(
                label="Download only not shadowbanned as Excel",
                data=excel_not_shadowbanned,
                file_name=f"not_shadowbanned_only_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.download_button(
                label="Download all as ZIP",
                data=(lambda: (lambda buf: (lambda z: (z.writestr('shadowban_results.xlsx', excel_all.getvalue()), z.writestr('shadowbanned_only.xlsx', excel_shadowbanned.getvalue()), z.writestr('not_shadowbanned_only.xlsx', excel_not_shadowbanned.getvalue()), buf.seek(0), buf.read())[4])(zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED)) or buf)(io.BytesIO()))(),
                file_name=f"shadowban_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                mime="application/zip"
            ) 