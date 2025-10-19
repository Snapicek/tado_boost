DOMAIN = "tado_boost"
PLATFORMS = []
CONF_REFRESH_TOKEN = "refresh_token"
OAUTH2_AUTHORIZE = "https://auth.tado.com/oauth/authorize"
OAUTH2_TOKEN = "https://auth.tado.com/oauth/token"
OAUTH2_SCOPES = ["home.user:all"]
# Optional: set your registered OAuth client_id and client_secret here if you
# registered an application with Tado. If left empty, users will need to
# register their own application and the flow may prompt for client details.
OAUTH2_CLIENT_ID = "<your_tado_client_id>"
OAUTH2_CLIENT_SECRET = "<your_tado_client_secret>"
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_BOOST_MINUTES = 15
DATA_COORDINATOR = "coordinator"
API_CLIENT = "api_client"
