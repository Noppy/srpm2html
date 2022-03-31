# srpm2html tool
## NAME
Generate a HTML from a SRPM source package.
## SYNOPSIS
    usage: srpm_to_html.py [-h] [-d] [-t TMPDIR] [-r RPMBUILDDIR] [-s SQUASHFSDIR]
                           [-K HTTP_KERNELSDIR] [-T HTTP_TOOLSDIR] [-S SOURCEDIR]
                           SRPM_FilePath_or_URL
## DESCRIPTION
- positional arguments:
    - SRPM_FilePath_or_URL  specify a Source Package(SRPM)'file path or URL.

- optional arguments:
    - -h, --help : show this help message and exit
    - -d, --debug : show some debugging output
    - -t TMPDIR, --tmpdir TMPDIR : specify a working directory(Used for downloading a srpm file and creating additional fstab file.)
    - -r RPMBUILDDIR, --rpmbuilddir RPMBUILDDIR : specify rpmbuild topdir
    - -s SQUASHFSDIR, --squashfsdir SQUASHFSDIR : specify squashfs directory
    - -K HTTP_KERNELSDIR, --http_kernelsdir HTTP_KERNELSDIR : specify directory which is the parent of kernel's html mount point
    - -T HTTP_TOOLSDIR, --http_toolsdir HTTP_TOOLSDIR : specify directory which is the parent of other's html mount point
    - -S SOURCEDIR, --sourcedir SOURCEDIR : specify source code directory

## Pequired directory structure(In the no optional argument spcification)
- /tmp
- /data/rpmbuild
- /data/squshfs
- /data/kernel
- /data/tools
- /data/source

## Required environment
- Required Pakages
    - rpm-build
    - squashfs-tools
    - gcc (※1)
    - make (※1)
    - ncurses-devel (※1)
    (※1) for making global
- Required OSS tools
    - Gnu global
- Procedure for creating the Gnu global tool
    1.download the Gnu global tool's source(http://tamacom.com/global/global-6.5.6.tar.gz)
    2.unpackage download file
    3.make & install
```
$ ./configure
$ make
$ sudo make install
```




## Set up by Ansible 
### Run EC2 instance

### Preparation
- Install git and Ansible
```shell
sudo yum -y install git
sudo amazon-linux-extras install -y ansible2
```
- Clone git repo
```shell
git clone https://github.com/Noppy/srpm2html.git
cd srpm2html/ansible
```
### Run Ansible play-book
```shell
#In the case of Nitro instances(ex. m5,c5...)
EbsDevName="/dev/vme1n1"
PartitionDevName="/dev/vme1n1p1"
#In the case of Xen instances(ex. m4,c4...)
EbsDevName="/dev/xvdb"
PartitionDevName="/dev/xvdb1"

#Run ansible playbook
ansible-playbook srpm2html.yml --extra-vars "EbsDevName=${EbsDevName} PartitionDevName=${PartitionDevName}" -i inventory
```
