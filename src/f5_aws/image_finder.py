import re
import boto
import boto.ec2
import collections

class BigIpImageFinder(object):
    def __init__(self):
        pass

    def searchitem(self, keys, name):
        value = None
        for k in keys:
            match = re.search('({})'.format(k), name)
            if match:
                value = match.group(1)
                break
        return value

    def getImagesForRegion(self, region):
        """
            Takes the name of an amazon region and retrieves a list of all
            images published by F5 for this region. 
            Formats a return object
        """

        #get all the images
        arg_s = ['aws', 'ec2', 'describe-images',
          '--region', region, '--filter',
          'Name=name,Values=\'F5*\'', '--output=json']
        
        conn = boto.ec2.connect_to_region(region)
        images = conn.get_all_images(filters={'name':'F5*'})

        #dimensions
        packages = ['good', 'better', 'best']
        throughputs = ['[0-9]+gbps', '[0-9]+mbps']
        licenses = ['byol', 'hourly']
        versions = [
            # 11.6.0.1.0.403-hf1
            '[0-9]+[.][0-9]+[.][0-9]+[.][0-9]+[.][0-9]+[.][0-9]+[-hf]*[0-9]*', 
            # 11.4.1-649.0-hf5
            '[0-9]+[.][0-9]+[.][0-9]+[-][0-9]+[.][0-9]+[-hf]*[0-9]*' 
        ]

        structured = []
        for i in images:
            try:
                image_name = i.name.lower()
                image_id = i.id.lower()

                license = self.searchitem(licenses, image_name)
                version = self.searchitem(versions, image_name)
                throughput = self.searchitem(throughputs, image_name)
                package = self.searchitem(packages, image_name)

                structured.append({
                    'name': image_name,
                    'id': image_id,
                    'version': version,
                    'package': package,
                    'license': license,
                    'throughput': str(throughput)})

            except Exception, e:
                print 'Failed processing image "{}". Will not be added to index. Error was {}'.format(image_name, e)

        return structured

    def find(self, **kwargs):
        images = self.getImagesForRegion(region=kwargs['region'])
        if kwargs['package'] is not None:
            images = [i for i in images if i['package'] == kwargs['package']]

        if kwargs['license'] is not None:
            images = [i for i in images if i['license'] == kwargs['license']]

        if kwargs['license'] == 'hourly' and kwargs['throughput'] is not None:
            images = [i for i in images if i['throughput'] == kwargs['throughput']]

        if kwargs['version'] is not None:
            images = [i for i in images if i['version'] is not None and
            re.match('^({})'.format(kwargs['version']), i['version'])]

        def byName_version(image):
            return image['version']
        try: 
            return sorted(images, key=byName_version, reverse=kwargs['take_newest'])
        except KeyError:
            return sorted(images, key=byName_version, reverse=True)