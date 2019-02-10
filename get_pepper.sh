#!/bin/bash
# this script downloads and unzips pepper.
# needs parameter MODULE_HOME (module workspace)
if [[ -z $1 ]]; then
	echo "Error: No module workspace provided."
	exit
fi
corpushome=$(pwd)
echo $corpushome
exbmodulepath="$1""pepperModules-EXMARaLDAModules/"
ruegmodulepath="$1""pepperModules-RUEGModules/"
textgridmodulepath="$1""pepperModules-TextGridModules/"
curl -X GET https://korpling.german.hu-berlin.de/saltnpepper/pepper/download/snapshot/Pepper_2018.12.20-SNAPSHOT.zip --output pepper.zip
unzip pepper.zip
cd pepper/
configdropins="$ruegmodulepath""target/,""$exbmodulepath""target/,""$textgridmodulepath""target"
echo $configdropins
echo "" >> conf/pepper.properties
echo "pepper.dropin.paths=""$configdropins" >> conf/pepper.properties
cd ..
rm pepper.zip
cd "$1"
modulehome=$(pwd)
if [[ ! -d "$exbmodulepath" ]]; then
	git clone git@github.com:korpling/pepperModules-EXMARaLDAModules -b develop
fi
cd $exbmodulepath
mvn clean install -DskipTests
cd $modulehome
if [[ ! -d "$ruegmodulepath" ]]; then
	git clone git@github.com:korpling/pepperModules-RUEGModules -b develop
fi
cd $ruegmodulepath
mvn clean install -DskipTests
cd $modulehome
if [[ ! -d "$textgridmodulepath" ]]; then
	git clone git@github.com:korpling/pepperModules-TextGridModules -b develop
fi
cd $textgridmodulepath
mvn clean install -DskipTests
cd "$corpushome"
echo "pepper installed successfully!"
