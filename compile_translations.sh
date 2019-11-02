#!/bin/sh

pygettext2.6.py -d pext_module_weather -a -- *.py

for dir in locale/*/LC_MESSAGES; do
    msgmerge -U -N "$dir/pext_module_weather.po" pext_module_weather.pot
    msgfmt "$dir/pext_module_weather.po" -o "$dir/pext_module_weather.mo"
done

python3 generate_metadata.py

# Copy to names with country code
#cp metadata_nl.json metadata_nl_NL.json
#cp metadata_es.json metadata_es_ES.json
