# Sync folders.
# Our VM will map the following directory to /home/vagrant if they are found.
# Update this to reflect your working directory structure.
module SyncPaths
  $repos = {
    "common" => "../common",
    "cloud" =>  "./",
  }
end
