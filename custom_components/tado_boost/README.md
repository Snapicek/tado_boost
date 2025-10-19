Tado Boost - custom Home Assistant integration

This integration provides a simple service `tado_boost.boost_all_zones` which will apply a 15-minute boost to all heating zones managed by Tado and then restore the original state.

Setup
- Add integration through Home Assistant UI and provide Tado username/password.

Service
- tado_boost.boost_all_zones
  - minutes (optional): number of minutes to boost (default 15)

Notes
- This is a minimal, functional example. Replace API endpoints and payloads in `api.py` with the real Tado API calls and add robust error handling as needed.
{
  "domain": "tado_boost",
  "name": "Tado Boost",
  "version": "1.0.0",
  "documentation": "https://example.com/tado_boost",
  "requirements": [],
  "dependencies": [],
  "codeowners": [],
  "config_flow": true,
  "iot_class": "cloud_polling"
}

