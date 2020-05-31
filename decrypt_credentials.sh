#!/bin/sh

gpg --quiet --batch --yes --decrypt --passphrase="$LABGRADER_PASSPHRASE" \
--output credentials.json credentials.json.gpg
