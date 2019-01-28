#!/bin/bash
# this script downloads and unzips pepper.
# needs parameter MODULE_HOME (module workspace)
if [[ -z $1 ]]; then
	echo "Error: No module workspace provided."
	exit
fi
corpushome=$pwd
exbmodulepath="$1""pepperModules-EXMARaLDAModules/target/"
ruegmodulepath="pepper.dropin.paths=""$1""pepperModules-RUEGModules/target/"
textgridmodulepath="$1""pepperModules-TextGridModules/target/"
curl -X GET https://korpling.german.hu-berlin.de/saltnpepper/pepper/download/snapshot/Pepper_2018.12.20-SNAPSHOT.zip --output pepper.zip
unzip pepper.zip
cd pepper/
echo "$ruegmodulepath"",""$exbmodulepath"",""$textgridmodulepath" >> conf/pepper.properties
cd ..
rm pepper.zip
cd "$1"
if [[ ! -e "$exbmodulepath" ]]:
	git clone git@github.com:korpling/pepperModules-EXMARaLDAModules -b develop
cd $exbmodulepath$
mvn clean install
if [[ ! -e "$ruegmodulepath" ]]:
	git clone git@github.com:korpling/pepperModules-RUEGModules -b develop
cd $ruegmodulepath$
mvn clean install
if [[ ! -e "$textgridmodulepath" ]]:
	git clone git@github.com:korpling/pepperModules-TextGridModules -b develop
cd $textgridmodulepath$
mvn clean install
cd "$corpushome"
echo "pepper installed successfully!"
