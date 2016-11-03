run:
ansible-playbook -i hosts freeswitch_server.yml --private-key=~/.ssh/endaga-test.pem -vvvv

testrun:
ansible-playbook -i hosts freeswitch_server.yml --private-key=~/.ssh/endaga-test.pem -C -vvvv

deploy local:
vagrant up

SSH:
ssh -i /home/kheimerl/.vagrant.d/insecure_private_key -S none -o StrictHostKeyChecking=no -o Port=2223 vagrant@127.0.0.1
