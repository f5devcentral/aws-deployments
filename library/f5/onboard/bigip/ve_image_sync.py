import os
import sys
import json
import urllib2
import urlparse
import argparse
import termios  # @UnresolvedImport
import fcntl

from distutils.util import strtobool
from distutils.spawn import find_executable
from odk.lib.nova import NovaLib
from odk.lib.glance import GlanceLib
from odk.lib.cinder import CinderLib

from odk.setup.common.args import ADMIN_CREDS_PARSER
from odk.setup.common.args import TENANT_CREDS_PARSER
from odk.setup.common.args import BASE_PARSER
from odk.setup.common.args import CRUD_PARSER
from odk.setup.common.args import set_base_globals
from odk.setup.common.args import set_crud_globals
from odk.setup.common.util import get_creds


class VEImageSync():
    """VE Image Synchronization Tool"""

    _image_dir = None

    _bookmark_protocol = 'https'
    _bookmark_host = 'raw.githubusercontent.com'
    _bookmark_path = 'f5openstackcommunity/f5veonboard/master/includes'
    _bookmark_file = 'bookmarks.json'
    _bookmark_url = "%s://%s/%s/%s" % (_bookmark_protocol,
                                       _bookmark_host,
                                       _bookmark_path,
                                       _bookmark_file)

    def __init__(self,
                 creds,
                 bookmarkfile,
                 workingdirectory,
                 interactive,
                 removefromglance):
        self._creds = creds
        self._bookmark_file = bookmarkfile
        self._image_dir = workingdirectory
        self._interactive = interactive
        self._removefromglance = removefromglance
        self._nova_admin = NovaLib(
            admin_creds=creds['admin'],
            tenant_creds=creds['tenant']
        ).nova_client
        self._glance_admin = GlanceLib(
            creds['admin'],
            creds['tenant']
        ).glance_client
        self._cinder_admin = CinderLib(
            creds['admin']
        ).cinder_client

    def _getch(self):
        """ Retrieve one character from stdin """
        fd = sys.stdin.fileno()
        oldterm = termios.tcgetattr(fd)
        newattr = termios.tcgetattr(fd)
        newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
        termios.tcsetattr(fd, termios.TCSANOW, newattr)
        oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)
        try:
            while 1:
                try:
                    c = sys.stdin.read(1)
                    break
                except IOError:
                    pass
        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)
            fcntl.fcntl(fd, fcntl.F_SETFL, oldflags)
        sys.stdout.write('\n')
        return c

    def _get_bookmark_data(self, workingdirectory):
        """ Find and parse the bookmarks JSON file """
        bookmarks = None
        if str(self._bookmark_file).startswith('http'):
            try:
                print "Downloading bookmark file: %s" % self._bookmark_file
                response = urllib2.urlopen(self._bookmark_file)
                if response.code == 200:
                    bookmarks = json.loads(response.read())
            except Exception as e:
                print "Can not download JSON file %s - %s" % \
                    (self._bookmark_file, e.message)
        elif self._bookmark_file and os.path.isfile(self._bookmark_file):
            bookmark_data = open(self._bookmark_file)
            try:
                bookmarks = json.loads(bookmark_data.read())
            except:
                print "Can not parse JSON file %s" % self._bookmark_file
            bookmark_data.close()
        elif os.path.isfile("%s/%s/%s" % (workingdirectory,
                                          'includes',
                                          self._bookmark_file)):
            bookmark_data = open("%s/%s/%s" % (workingdirectory,
                                               'includes',
                                               self._bookmark_file))
            try:
                bookmarks = json.loads(bookmark_data.read())
            except:
                print "Can not parse JSON file %s" % self._bookmark_file
            bookmark_data.close()
        else:
            try:
                print "Downloading bookmark file: %s" % self._bookmark_file
                response = urllib2.urlopen(self._bookmark_url)
                if response.code == 200:
                    bookmarks = json.loads(response.read())
            except:
                print "Can not download JSON file %s" % self._bookmark_url
        return bookmarks

    def _find_image_patch_tool(self):
        """ find the cli pathc-image.sh tool """
        # check system path
        patch_exe = find_executable('patch-image.sh')
        if patch_exe:
            return patch_exe
        # check f5-onboard standard directory
        patch_exe = find_executable(
            'patch-image.sh',
            '/usr/libexec/f5-onboard/ve/openstack/'
        )
        if patch_exe:
            return patch_exe
        # check location relative to the python file for development
        script_path = os.path.dirname(os.path.realpath(__file__))
        patch_exe = find_executable(
            'patch-image.sh',
            "%s/%s" % (script_path, '../../../../libexec/ve/openstack')
        )
        if patch_exe:
            return patch_exe
        # check location based on cwd
        cwd = os.getcwd()
        patch_exe = find_executable(
            'patch-image.sh',
            "%s/%s" % (cwd, '../libexec/ve/openstack')
        )
        if patch_exe:
            return patch_exe
        return None

    def _download_f5_images(self, f5_image, target_directory=None):
        """ Download f5 disk and iso images based on bookmark URLs """
        if not target_directory:
            target_directory = self._image_dir
        if not os.path.isdir(target_directory):
            os.mkdir(target_directory)
        # download all url file in the image bookmark
        for url in f5_image['urls']:
            # This only works if the server produced last-modified which
            # our download servers do not currently. Opted for 'no clubber'
            # instead of downloading every time.
            # cmd = "wget --quiet -t 10 -c -N -P %s --content-disposition %s" \
            #      % ("%s/%s" % (target_directory, '/images/added'), url)
            cmd = "wget -q -t 10 -c -nc -O %s/%s %s" \
                  % ("%s/%s" % (target_directory, 'images/added/'),
                     os.path.basename(urlparse.urlparse(url).path),
                     url)
            print "Downloading %s" % url
            os.system(cmd)
        # validate we have all the files from the urls
        have_all_files = True
        # required to have the container file at least (zip file)
        if not os.path.isfile(
                "%s/%s/%s" % (target_directory,
                              'images/added',
                              f5_image['container_file_name'])):
            have_all_files = False

        # Functionality removed because patching is now done by VE team
        # You can issues a presales ticket to get the patched KVM image

        # if not f5_image['base_iso_file'] == 'none':
        #    if not os.path.isfile(
        #            "%s/%s" % (target_directory, f5_image['base_iso_file'])):
        #        have_all_files = False

        # if not f5_image['hf_iso_file'] == 'none':
        #    if not os.path.isfile(
        #            "%s/%s" % (target_directory, f5_image['hf_iso_file'])):
        #        have_all_files = False

        if have_all_files:
            return True
        else:
            return False

    def _find_startup_agent_script(self, startupfile):
        """ Find the referenced bookmark startup agent script file """
        if str(startupfile).startswith('http'):
            cmd = "wget -q -t 10 -c -r -O %s/%s --content-disposition %s" \
                  % ("%s/%s" % (self._image_dir, 'includes'),
                     os.path.basename(urlparse.urlparse(startupfile).path),
                     startupfile)
            print "Downloading %s" % startupfile
            print "cmd: %s" % cmd
            os.system(cmd)
            return "%s/%s/%s" % (self._image_dir,
                                 'includes',
                                 os.path.basename(startupfile))
        if os.path.isfile(startupfile):
            return startupfile
        if os.path.isfile(startupfile):
            return startupfile
        script_path = os.path.dirname(os.path.realpath(__file__))
        cwd = os.getcwd()
        # look in cwd
        if os.path.isfile("%s/%s" % (cwd, startupfile)):
            return "%s/%s" % (cwd, startupfile)
        # look in cwd /includes
        if os.path.isfile("%s/%s/%s" % (cwd,
                                        'includes',
                                        startupfile)):
            return "%s/%s/%s" % (cwd,
                                 'includes',
                                 startupfile)
        # look for scriptdir/
        if os.path.isfile("%s/%s" % (script_path, startupfile)):
            return "%s/%s" % (script_path, startupfile)
        # look for scriptdir /includes
        if os.path.isfile("%s/%s/%s" % (script_path,
                                        'includes',
                                        startupfile)):
            return "%s/%s/%s" % (script_path, 'includes', startupfile)
        # look for working directory
        if os.path.isfile("%s/%s" % (self._image_dir, startupfile)):
            return "%s/%s" % (self._image_dir, startupfile)
        # look in working directory /includes
        if os.path.isfile("%s/%s/%s" % (self._image_dir,
                                        'includes',
                                        startupfile)):
            return "%s/%s/%s" % (self._image_dir,
                                 'includes',
                                 startupfile)
        # look in default f5-onboard directory
        if os.path.isfile(
                "%s/%s" % ('/usr/lib/f5-onboard/images', startupfile)):
            return "%s/%s" % ('/usr/lib/f5-onboard/images', startupfile)
        return None

    def _find_userdata_file(self, userdatafile):
        """ Find the referenced bookmark userdata policy script file """
        if str(userdatafile).startswith('http'):
            cmd = "wget -q -t 10 -c -r -O %s/%s --content-disposition %s" \
                  % ("%s/%s" % (self._image_dir, 'includes'),
                     os.path.basename(urlparse.urlparse(userdatafile).path),
                     userdatafile)
            print "Downloading %s" % userdatafile
            print "cmd: %s" % cmd
            os.system(cmd)
            return "%s/%s/%s" % (self._image_dir,
                                 'includes',
                                 os.path.basename(userdatafile))
        if os.path.isfile(userdatafile):
            return userdatafile
        # look for a full path
        script_path = os.path.dirname(os.path.realpath(__file__))
        cwd = os.getcwd()
        # look in cwd
        if os.path.isfile("%s/%s" % (cwd, userdatafile)):
            return "%s/%s" % (cwd, userdatafile)
        # look in cwd /includes
        if os.path.isfile("%s/%s/%s" % (cwd,
                                        'includes',
                                        userdatafile)):
            return "%s/%s/%s" % (cwd,
                                 'includes',
                                 userdatafile)
        # look for scriptdir/
        if os.path.isfile("%s/%s" % (script_path, userdatafile)):
            return "%s/%s" % (script_path, userdatafile)
        # look for scriptdir /includes
        if os.path.isfile("%s/%s/%s" % (script_path,
                                        'includes',
                                        userdatafile)):
            return "%s/%s/%s" % (script_path, 'includes', userdatafile)
        # look for working directory
        if os.path.isfile("%s/%s" % (self._image_dir, userdatafile)):
            return "%s/%s" % (self._image_dir, userdatafile)
        # look in working directory /includes
        if os.path.isfile("%s/%s/%s" % (self._image_dir,
                                        'includes',
                                        userdatafile)):
            return "%s/%s/%s" % (self._image_dir,
                                 'includes',
                                 userdatafile)
        # look in default f5-onboard directory
        if os.path.isfile(
                "%s/%s" % ('/usr/lib/f5-onboard/images', userdatafile)):
            return "%s/%s" % ('/usr/lib/f5-onboard/images', userdatafile)
        return None

    def _setup(self):
        """ Setup before the image patch process """
        pass

    def _tear_down(self):
        """ Tear down after the image patch process """
        pass

    def _create_volume_type(self):
        """ Create f5 cinder volume type with extra data for DATASTORs """
        for vt in self._cinder_admin.volume_types.list():
            if vt.name == 'F5.DATASTOR':
                break
        else:
            vt = self._cinder_admin.volume_types.create('F5.DATASTOR')
            vt.set_keys({'type': 'datastor'})
            vt.set_keys({'vendor': 'f5_networks'})

    def _extract_disk_images(self, f5_image):
        """ Unzip the disk images from the downloaded zip container """
        container_dir = "%s/%s" % (self._image_dir, 'images/added')
        extract_dir = "%s/%s" % (self._image_dir, 'images/patched')
        # unzip image container
        if os.path.isfile("%s/%s" % (container_dir,
                                     f5_image['container_file_name'])):
            if f5_image['container_file_name'].endswith('.zip'):
                uzcmd = "unzip -o -d %s %s %s" % (
                        extract_dir,
                        "%s/%s" % (container_dir,
                                   f5_image['container_file_name']),
                        f5_image['disk_image_file']
                )
                os.system(uzcmd)
                for volume in f5_image['volumes']:
                    for image_file in volume.keys():
                        volume_file = volume[image_file]['volume_file']
                        uzcmd = "unzip -o -d %s %s %s" % (
                                extract_dir,
                                "%s/%s" % (container_dir,
                                           f5_image['container_file_name']),
                                volume_file
                        )
                        os.system(uzcmd)

        # Functionality removed because patching is now done by VE team
        # You can issues a presales ticket to get the patched KVM image

        # if not f5_image['base_iso_file'] == 'none':
        #    if not os.path.isfile("%s/%s" % (target_directory,
        #                                     f5_image['base_iso_file'])):
        #        if os.path.isfile("%s/%s" % (self._image_dir,
        #                                     f5_image['base_iso_file'])):
        #            shutil.copy2("%s/%s" % (self._image_dir,
        #                                    f5_image['base_iso_file']),
        #                         "%s/%s" % (target_directory,
        #                                    f5_image['base_iso_file']))

        # if not f5_image['hf_iso_file'] == 'none':
        #    if not os.path.isfile("%s/%s" % (target_directory,
        #                                     f5_image['hf_iso_file'])):
        #        if os.path.isfile("%s/%s" % (self._image_dir,
        #                                     f5_image['hf_iso_file'])):
        #            shutil.copy2("%s/%s" % (self._image_dir,
        #                                    f5_image['hf_iso_file']),
        #                         "%s/%s" % (target_directory,
        #                                    f5_image['hf_iso_file']))

    def _create_disk_image(self, f5_image):
        """ Create a glance image using the patch image utility"""
        extract_dir = "%s/%s" % (self._image_dir, 'images/patched')
        # validate image definition from bookmark
        create_image = True
        # do we have a patch_image script?
        patch_tool = self._find_image_patch_tool()
        if not patch_tool:
            print "Can not find the image patch utility."
            create_image = False
        # do we have a startup script?
        startup_script = self._find_startup_agent_script(
            f5_image['startup_script']
        )
        if not startup_script:
            print "No startup agent script %s found." % startup_script
            create_image = False
        # can we find the required userdata policy file?
        userdata_file = self._find_userdata_file(
            f5_image['default_userdata']
        )
        if not userdata_file:
            print "No default user data: %s found." % userdata_file
            create_image = False
        # did the image get extracted to the proper directory?
        image_file = '%s/%s' % (extract_dir, f5_image['disk_image_file'])
        if not os.path.isfile(image_file):
            print "Disk file image %s not found." % image_file
            create_image = False
        # if all validation passes.. create image.. if not don't.
        if not create_image:
            print "Can not create image. Requirements not met."
            return False
        # build patch image command
        create_image_cmd = "sudo /bin/bash %s " % patch_tool
        if f5_image['firstboot_flag_file'] == 'true':
            create_image_cmd += '-f '
        create_image_cmd += "-s \"%s\" " % startup_script
        create_image_cmd += "-u \"%s\" " % userdata_file
        create_image_cmd += "-t \"%s\" " % extract_dir
        create_image_cmd += "-o \"%s\" " % f5_image['image_name']
        create_image_cmd += " \"%s\" " % image_file
        print "Issuing Command: %s" % create_image_cmd
        # run patch image command
        os.system(create_image_cmd)
        # create image metadata
        properties = {}
        properties['os_name'] = f5_image['os_name']
        properties['os_type'] = f5_image['os_type']
        properties['os_vendor'] = f5_image['os_vendor']
        properties['os_version'] = f5_image['os_version']
        properties['nova_flavor'] = f5_image['flavor']
        properties['description'] = f5_image['image_description']
        # create glance image
        new_image = self._glance_admin.images.create(
            name=f5_image['image_name'],
            disk_format=f5_image['disk_format'],
            container_format=f5_image['container_format'],
            min_disk=f5_image['min-disk'],
            min_ram=f5_image['min-ram'],
            properties=properties,
            is_public='true'
        )
        print "Glance image %s with id %s created" % (new_image.name,
                                                      new_image.id)
        new_image_file = "%s/%s" % (extract_dir,
                                    f5_image['image_name'])
        print "Uploading %s to image %s" % (new_image_file, new_image.id)
        # upload the image
        new_image.update(data=open(new_image_file, 'rb'))
        print "Removing temporary build image %s" % new_image_file
        # delete the patch file
        os.unlink(new_image_file)

    def _create_flavor(self, f5_image):
        """ Create the named nova flavor from the bookmark entry """
        for flavor in self._nova_admin.flavors.list():
            if f5_image['flavor'] == flavor.name:
                break
        else:
            flavor = self._nova_admin.flavors.create(
                name=f5_image['flavor'],
                vcpus=f5_image['vcpus'],
                ram=f5_image['min-ram'],
                disk=f5_image['min-disk'],
                is_public=True
            )
            flavor.set_keys({'flavor_vendor': 'f5_networks'})

    def _create_volumes(self, f5_image):
        """ Create volume images for f5 DATASTORs """
        extract_dir = "%s/%s" % (self._image_dir, 'images/patched')
        if 'volumes' in f5_image and f5_image['volumes']:
            glance_images = self._glance_admin.images.list()
            for volume in f5_image['volumes']:
                for vi_name in volume.keys():
                    for image in glance_images:
                        if image.name == vi_name:
                            break
                    else:
                        volume_file = volume[vi_name]['volume_file']
                        if os.path.isfile("%s/%s" % (extract_dir,
                                                     volume_file)):
                            properties = {}
                            properties['os_name'] = f5_image['os_name']
                            properties['os_type'] = 'f5bigip_datastor'
                            properties['os_vendor'] = f5_image['os_vendor']
                            properties['os_version'] = f5_image['os_version']
                            properties['description'] = \
                                'DATASTOR image for %s' % f5_image['name']
                            f5vi = volume[vi_name]
                            new_image = \
                                self._glance_admin.images.create(
                                    name=vi_name,
                                    disk_format=f5vi['disk_format'],
                                    container_format=f5vi['container_format'],
                                    min_disk=f5vi['min-disk'],
                                    properties=properties,
                                    is_public='true'
                                )
                            print "Glance image %s with id %s created" % (
                                new_image.name,
                                new_image.id
                            )
                            new_image_file = "%s/%s" % (extract_dir,
                                                        volume_file)
                            print "Uploading %s to image %s" % (new_image_file,
                                                                new_image.id)
                            new_image.update(data=open(new_image_file, 'rb'))

    def _download_from_bookmarks(self):
        """ Download images present in the bookmarks file """
        bookmarks = self._get_bookmark_data(self._image_dir)
        if bookmarks:
            f5_images = bookmarks['bookmarks']
            for f5_image in f5_images:
                download_image = True
                if self._interactive:
                    sys.stdout.write(
                        "Download %s Containers? [y/n]: "
                        % f5_image['name'])
                    download_image = strtobool(self._getch())
                if download_image:
                    if self._download_f5_images(f5_image):
                        print "Could not download image %s" % f5_image['urls']
                        sys.exit(1)

    def _sync_from_bookmarks(self):
        """ Synchronize the bookmarks file to glance images and nova flavors"""
        bookmarks = self._get_bookmark_data(self._image_dir)
        if bookmarks:
            f5_images = bookmarks['bookmarks']
            f5_disk_images_to_add = []
            f5_volume_images_to_add = []
            f5_images_to_remove = []
            images = list(self._glance_admin.images.list())
            existing_image_names = []
            bookmark_image_names = []
            volume_image_names = []
            for image in images:
                existing_image_names.append(image.name)
            for f5_image in f5_images:
                bookmark_image_names.append(f5_image['image_name'])
                if f5_image['volumes']:
                    for vi in f5_image['volumes']:
                        for image_name in vi.keys():
                            volume_image_names.append(image_name)
                            if image_name not in existing_image_names and \
                               image_name not in f5_volume_images_to_add:
                                f5_volume_images_to_add.append(image_name)
                if not f5_image['image_name'] in existing_image_names:
                    f5_disk_images_to_add.append(f5_image)
            if self._removefromglance:
                for image in images:
                    if 'os_vendor' in image.properties and \
                       image.properties['os_vendor'] == 'f5_networks':
                        if image.name not in bookmark_image_names and \
                           image.name not in volume_image_names:
                            f5_images_to_remove.append(image)
                for image in f5_images_to_remove:
                    remove_image = True
                    if self._interactive:
                        sys.stdout.write(
                            "Remove %s Glance Image? [y/n]: "
                            % image.name)
                        remove_image = strtobool(self._getch())
                    if remove_image:
                        try:
                            self._glance_admin.images.delete(image.id)
                        except:
                            print('Could not delete %s Glance image.'
                                  % image.name)
            # base sync setup
            self._setup()
            # always check that datastor volume type created
            self._create_volume_type()
            for f5_image in f5_disk_images_to_add:
                add_image = True
                if self._interactive:
                    sys.stdout.write(
                        "Add %s Glance Image? [y/n]: "
                        % f5_image['name'])
                    add_image = strtobool(self._getch())
                if add_image:
                    if self._download_f5_images(f5_image):
                        # unzip container disk
                        self._extract_disk_images(f5_image)
                        # reauth everything because downloading
                        # multi Gig files will often take much
                        # longer then the token valid period
                        self._nova_admin = NovaLib(
                            admin_creds=self._creds['admin'],
                            tenant_creds=self._creds['tenant']
                        ).nova_client
                        self._glance_admin = \
                            GlanceLib(
                                self._creds['admin'],
                                self._creds['tenant']
                            ).glance_client
                        self._cinder_admin = \
                            CinderLib(self._creds['admin']).cinder_client
                        self._create_disk_image(f5_image)
                        self._create_flavor(f5_image)
                        if f5_image['volumes']:
                            for vi in f5_image['volumes']:
                                for image_name in vi.keys():
                                    if image_name in f5_volume_images_to_add:
                                        self._create_volumes(f5_image)
                                        f5_volume_images_to_add.remove(
                                            image_name
                                        )
                    else:
                        print "%s download failed." % f5_image['name']
            # Create volume images
            considered_volumes = []
            for vi_image in f5_volume_images_to_add:
                for f5_image in f5_images:
                    if f5_image['volumes']:
                        for vi in f5_image['volumes']:
                            for image_name in vi.keys():
                                if image_name == vi_image and \
                                   image_name not in considered_volumes:
                                    add_image = True
                                    if self._interactive:
                                        sys.stdout.write(
                                            "Add %s Glance Image? [y/n]: "
                                            % image_name)
                                        add_image = strtobool(self._getch())
                                    if add_image:
                                        self._extract_disk_images(f5_image)
                                        self._create_volumes(f5_image)
                                    considered_volumes.append(image_name)
            # base sync tear_down
            self._tear_down()


def main(argv=None):
    if argv is None:
        argv = sys.argv
    PARSER = argparse.ArgumentParser(parents=[ADMIN_CREDS_PARSER,
                                              BASE_PARSER,
                                              CRUD_PARSER,
                                              TENANT_CREDS_PARSER])
    PARSER.add_argument(
        '-b', '--bookmarkfile',
        default='bookmarks.json',
        help='JSON file containing TMOS Virtual Edition references.'
    )
    PARSER.add_argument(
        '-r', '--removefromglance',
        action="store_true",
        help='Remove images from Glance which are not in the bookmarks file.'
    )
    PARSER.add_argument(
        '-w', '--workingdirectory',
        default="%s/.f5-onboard" % os.environ['HOME'],
        help='Directory to save working files.'
    )
    PARSER.add_argument(
        '-i', '--interactive',
        action="store_true",
        help='Get synchronization authorization from CLI'
    )
    PARSER.add_argument(
        '-d', '--downloadonly',
        action="store_true",
        help='Only download bookmark container files, do not synchronize.'
    )

    ARGS = PARSER.parse_args()

    bookmarkfile = ARGS.bookmarkfile

    workingdirectory = ARGS.workingdirectory
    interactive = False
    if ARGS.interactive:
        interactive = True
    removefromglance = False
    if ARGS.removefromglance:
        removefromglance = True
    downloadonly = False
    if ARGS.downloadonly:
        downloadonly = True

    set_base_globals(
        openstack_api_endpoint=ARGS.openstack_api_endpoint,
        verbose=ARGS.verbose
    )

    set_crud_globals(
        check=ARGS.check,
        sleep=ARGS.sleep
    )

    creds = get_creds(ARGS)

    print "Creating Synchronization Client"
    image_sync_client = VEImageSync(creds,
                                    bookmarkfile,
                                    workingdirectory,
                                    interactive,
                                    removefromglance)

    if downloadonly:
        image_sync_client._download_from_bookmarks()
    else:
        image_sync_client._sync_from_bookmarks()


if __name__ == '__main__':
    main()
