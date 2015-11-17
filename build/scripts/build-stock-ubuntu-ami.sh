#!/bin/bash -ex

#########################
# Build Base AMI for an F5 AWS Deployments Server.
#
# Adapted from
# alestic-git-build-ami
# in https://github.com/alestic/alestic-git
##
# This script expects to run on an existing EC2 instance with awscli
# Credentials should be stored in 
#          ~/.aws/credentials
# according to awscli specs
#  ex. cat ~/.aws/credentials 
#      [default]
#      aws_access_key_id = <your_aws_key_here>
#      aws_secret_access_key = <your_secret_key_here>
#
#  ex. 
#  build-stock-ubuntu-ami.sh --codename $codename     \
#                           --brand "$brand"         \
#                           --size "$size"           \
#                           --now "$now"         2>&1 |
#      tee $brand-$codename-$region-$arch2.log
#
#  ex. interpolated
#  ./build-stock-ubuntu-ami.sh --codename "trusty" --brand "F5-AWS-Deployments" --size "8" --now "$now" 2>&1 | tee F5-AWS-Deployments-trusty-us-west-2-amd64.log
###############################

# Defaults

# Brand used in AMI name and description
brand="F5-AWS-Deployments"

# Size of AMI file system
size=8 # GB

# Ubuntu release
codename=trusty

# AMI name timestamp
now=$(date -u +%Y%m%d-%H%M)

# aws cli credentials
export AWS_CONFIG_FILE=/home/ubuntu/.aws

# path for virtenv aws cli
# as sudo doesn't see aliases
AWS_COMMAND=$(which aws)


# Command line options
while [ $# -gt 0 ]; do
  case $1 in
    --brand)       brand=$2;     shift 2 ;;
    --size)        size=$2;      shift 2 ;;
    --codename)    codename=$2;  shift 2 ;;
    --now)         now=$2;       shift 2 ;;
    *)             echo "$0: Unrecognized option: $1" >&2; exit 1;
  esac
done

# Setup
case $codename in
  maverick)   release=10.10     ;;
  natty)      release=11.04     ;;
  oneiric)    release=11.10     ;;
  precise)    release=12.04     ;;
  quantal)    release=12.10     ;;
  trusty)     release=14.04     ;;
  *)          echo "$0: Unrecognized codename: $codename" >&2; exit 1;
esac

if [ $(uname -m) = 'x86_64' ]; then
  arch=x86_64
  arch2=amd64
  ephemeraldev=/dev/sdb
else
  arch=i386
  arch2=i386
  ephemeraldev=/dev/sda2
fi

name="${brand}-${release}-${codename}-${arch2}"
description="${brand} Ubuntu ${release} ${codename} ${arch2}"

#export EC2_CERT=$(echo /mnt/cert-*.pem)
#export EC2_PRIVATE_KEY=$(echo /mnt/pk-*.pem)

imagename=$codename-server-cloudimg-$arch2
imageurl=http://cloud-images.ubuntu.com/$codename/current/$imagename.tar.gz
amisurl=http://cloud-images.ubuntu.com/query/$codename/server/released.current.txt
zoneurl=http://instance-data/latest/meta-data/placement/availability-zone

# Sometimes, instance-data does not resolve right away.
# Loop to give it some time.
while zone=$(wget -qO- $zoneurl);
      test "$zone" = ""
do
  sleep 30
done; echo " $zone"

region=$(echo $zone | perl -pe 's/.$//')
akiid=$(wget -qO- $amisurl | egrep "ebs.$arch2.$region.*paravirtual" | cut -f9)
#ariid=$(wget -qO- $amisurl | egrep "ebs.$arch2.$region.*paravirtual" | cut -f10)

# Set the default region for aws cli to our current region
export AWS_DEFAULT_REGION=$region

# Update and install Ubuntu packages
export DEBIAN_FRONTEND=noninteractive
sudo perl -pi -e 's/^# *(deb .*multiverse)$/$1/' /etc/apt/sources.list

# Instance used already has this installed
# Otherwise, should uncomment
#sudo apt-get update
#sudo -E apt-get upgrade -y
sudo apt-get install -y python-pip
sudo pip install awscli

# Download base Ubuntu server image built by Canonical
image=/mnt/$imagename.img
imagedir=/mnt/$codename-cloudimg-$arch2
wget -qO- $imageurl |
  sudo tar xzf - -C /mnt
sudo mkdir -p $imagedir
sudo mount -o loop $image $imagedir

# Allow network access from chroot environment
sudo mkdir -p $imagedir/run/resolvconf
sudo cp /etc/resolv.conf $imagedir/run/resolvconf/resolv.conf
#sudo cp /etc/resolv.conf $imagedir/etc/resolvconf/resolv.conf.d/tail

# We used XFS for the target root file system
#sudo perl -pi -e 's%(\t/\t)ext4(\t)%${1}xfs${2}%' $imagedir/etc/fstab

# Upgrade and install packages on the target file system
sudo chroot $imagedir mount -t proc none /proc
#sudo chroot $imagedir mount -t devpts none /dev/pts
cat <<EOF | sudo tee $imagedir/usr/sbin/policy-rc.d > /dev/null
#!/bin/sh
exit 101
EOF
sudo chmod 755 $imagedir/usr/sbin/policy-rc.d
DEBIAN_FRONTEND=noninteractive
sudo perl -pi -e 's/^# *(deb .*multiverse)$/$1/' \
  $imagedir/etc/apt/sources.list                 \
  $imagedir/etc/cloud/templates/sources.list.ubuntu.tmpl
#sudo chroot $imagedir add-apt-repository ppa:alestic
sudo chroot $imagedir apt-get update
sudo -E chroot $imagedir apt-get dist-upgrade -y

# This is great idea and best practices but commenting out 
# don't want to risk breaking demo for now due
# to unexpected changes/dependencies
#
# Install software
#sudo -E chroot $imagedir    
#  apt-get install -y        \
#    coreutils               \
#     unattended-upgrades     \
# 
# # Apply Ubuntu security patches daily
# cat <<EOF | sudo tee $imagedir/etc/apt/apt.conf.d/10periodic > /dev/null
# APT::Periodic::Update-Package-Lists "1";
# APT::Periodic::Download-Upgradeable-Packages "1";
# APT::Periodic::AutocleanInterval "7";
# APT::Periodic::Unattended-Upgrade "1";
# EOF

# Clean up chroot environment
sudo chroot $imagedir umount /proc
#sudo chroot $imagedir umount /dev/pts
sudo rm -f $imagedir/usr/sbin/policy-rc.d
sudo rm -f $imagedir/run/resolvconf/resolv.conf

# Create and mount temporary EBS volume with file system to hold new AMI image
volumeid=$(sudo -E $AWS_COMMAND ec2 create-volume \
             --availability-zone "$zone" \
             --size "$size"              \
             --volume-type gp2           \
             --output text               \
             --query 'VolumeId' )
while sudo -E $AWS_COMMAND ec2 describe-volumes \
        --volume-id "$volumeid" \
        --output text \
        --query 'Volumes[*].State' |
      grep -v -q available
  do sleep 3; done
instance_id=$(wget -qO- http://instance-data/latest/meta-data/instance-id)
sudo -E $AWS_COMMAND ec2 attach-volume   \
   --device /dev/sdi            \
   --instance-id "$instance_id" \
   --volume-id "$volumeid"      \
   --output text                \
   --query 'State'
dev=/dev/xvdi
while [ ! -e $dev ]
  do sleep 3; done
sudo mkfs.ext4 -L cloudimg-rootfs $dev
ebsimagedir=$imagedir-ebs
sudo mkdir -p $ebsimagedir
sudo mount $dev $ebsimagedir

# Copy file system from temporary rootdir to EBS volume
sudo tar -cSf - -C $imagedir . | sudo tar xvf - -C $ebsimagedir
sudo umount $imagedir
sudo umount $ebsimagedir
sudo -E $AWS_COMMAND ec2 detach-volume \
  --volume-id "$volumeid" \
  --output text \
  --query 'State'
while sudo -E $AWS_COMMAND ec2 describe-volumes \
        --volume-id "$volumeid" \
        --output text \
        --query 'Volumes[*].State' |
      grep -v -q available
  do sleep 3; done
snapshotid=$(sudo -E $AWS_COMMAND ec2 create-snapshot \
               --description "$name" \
               --volume-id "$volumeid" \
               --output text \
               --query 'SnapshotId' )
while sudo -E $AWS_COMMAND ec2 describe-snapshots \
        --snapshot-id "$snapshotid" \
        --output text \
        --query 'Snapshots[*].State' |
      grep pending
  do sleep 10; done

# Register the snapshot as a new AMI
block_device_mapping=$(cat <<EOF
[
  {
    "DeviceName": "/dev/sda1",
    "Ebs": {
      "DeleteOnTermination": true, 
      "SnapshotId": "$snapshotid",
      "VolumeSize": $size,
      "VolumeType": "gp2"
    }
  }, {
    "DeviceName": "$ephemeraldev",
    "VirtualName": "ephemeral0"
  }
]
EOF
)
amiid=$(sudo -E $AWS_COMMAND ec2 register-image            \
  --name "$name"                                  \
  --description "$description"                    \
  --architecture "$arch"                          \
  --kernel-id "$akiid"                            \
  --block-device-mapping "$block_device_mapping"  \
  --root-device-name "/dev/sda1"                  \
  --output text                                   \
  --query 'ImageId'
)

sudo -E $AWS_COMMAND ec2 delete-volume \
  --volume-id "$volumeid" \
  --output text

cat <<EOF
AMI: $amiid $codename $region $arch2

ami id:       $amiid
aki id:       $akiid
region:       $region ($zone)
architecture: $arch ($arch2)
os:           Ubuntu $release $codename
name:         $name
description:  $description
EBS volume:   $volumeid (deleted)
EBS snapshot: $snapshotid

ami_id=$amiid
snapshot_id=$snapshotid

Test the new AMI using something like:

  instance_id=\$(aws ec2 run-instances \\
    --region $region \\
    --key \$USER \\
    --instance-type t1.micro \\
    --image-id $amiid
    --output text \\
    --query 'Instances[*].InstanceId' )
  echo instance_id=\$instance_id

EOF
