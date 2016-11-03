#!/bin/bash

# This script should be run when you first bring up a dev VM. It'll drop you in
# to a virtual environment with all the requirements installed -- so you should
# be ready to `python manage.py migrate` and go!

if [ `whoami` != "vagrant" ]; then
  echo "Hey, you're not on a dev VM! Quitting."
  exit 1
fi

curl http://www.icanhazip.com
if [ $? -ne 0 ]; then
  echo "Looks like networking isn't working right. Try running 'vagrant provision web' from your dev server to fix."
  exit 2
fi

~/cloud/configs/deployment/scripts/install_dependencies
sudo pip install virtualenvwrapper
echo "source /usr/local/bin/virtualenvwrapper.sh" >> ~/.bashrc
source /usr/local/bin/virtualenvwrapper.sh
mkvirtualenv endaga
cd ~/cloud
pip install -r requirements.txt

echo ""
echo ">>>>> Setup complete. Logout, log back in, and run 'workon endaga' to get started! <<<<<"
