# Sync folders.
# Our VM will map the following directory to /home/vagrant if they are found.
# Update this to reflect your working directory structure.
module SyncPaths
  $repos = {
    "osmocom-python" => "../osmocom-python",
    "openbts" => "../openbts",
    "smqueue" => "../smqueue",
    "subscriberRegistry" => "../subscriberRegistry",
    "liba53" => "../liba53",
    "freeswitch" => "../freeswitch",
    "sms_utilities" =>  "../sms_utilities",
    "snowflake" =>  "../snowflake",
    "openbts-python" =>  "../openbts-python",
    "common" => "../common",
    "smspdu" => "../smspdu",
    "client" =>  "./",
  }
end
