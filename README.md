Tado Boost
============

Tado Boost is a small Home Assistant custom integration that adds a service to boost all Tado heating zones for a short period (default 15 minutes) and then restore their original states.

Installation (manual)
---------------------
1. Copy the `custom_components/tado_boost` folder to your Home Assistant `config` directory (where `configuration.yaml` lives).
2. Restart Home Assistant.
3. In the UI go to Settings -> Devices & Services -> Add Integration and search for "Tado Boost" and follow the setup.

Installation (HACS)
-------------------
To make this repository installable via HACS you can add it as a custom repository in HACS -> Integrations -> "+" -> "Custom repositories" and paste the repository URL. Select type "integration".

Usage
-----
Call the service `tado_boost.boost_all_zones` with optional `minutes` parameter to run the boost. Example in Developer Tools -> Services:

{
  "minutes": 15
}

Notes
-----
- The included `api.py` is a minimal placeholder and uses example endpoints. Replace with the official Tado API endpoints and proper OAuth flows if needed.
- For reauthorization the integration supports the config flow reauth UI.

Developers
----------
Replace occurrences of `<your-github-username>` with your GitHub handle in `manifest.json` and `CODEOWNERS`.

License
-------
This project is licensed under the MIT License - see the LICENSE file for details.

