"""
Copyright (c) 2016-present, Facebook, Inc.
All rights reserved.

This source code is licensed under the BSD-style license found in the
LICENSE file in the root directory of this source tree. An additional grant 
of patent rights can be found in the PATENTS file in the same directory.
"""

from datetime import datetime
from io import BytesIO

from django.core.files import File
from django.core.files.storage import Storage
from django.core.urlresolvers import reverse
from endagaweb.models import FileUpload


class DatabaseStorage(Storage):
    """
    Class DatabaseStorage provides storing files in the database.
    """

    def get_available_name(self, name, max_length=None):
        """
        Returns a filename that's free on the target storage system, and
        available for new content to be written to.
        """
        return name

    def path(self, name):
        """
        Returns a local filesystem path where the file can be retrieved using
        Python's built-in open() function. Storage systems that can't be
        accessed using open() should *not* implement this method.
        """
        raise NotImplementedError("This backend doesn't have paths.")


    def listdir(self, path):
        """
        Lists the contents of the specified path, returning a 2-tuple of lists;
        the first item being directories, the second item being files.
        """
        raise NotImplementedError("This backend doesn't have directories")


    def size(self, name):
        """
        Returns the total size, in bytes, of the file specified by name.
        """
        return FileUpload.objects.get(name=name).size


    def url(self, name):
        """
        Returns an absolute URL where the file's contents can be accessed
        directly by a Web browser.
        """
        return reverse('file-upload', kwargs={'fname': name})


    def accessed_time(self, name):
        """
        Returns the last accessed time (as datetime object) of the file
        specified by name.
        """
        return FileUpload.objects.get(name=name).accessed_time


    def created_time(self, name):
        """
        Returns the creation time (as datetime object) of the file
        specified by name.
        """
        return FileUpload.objects.get(name=name).created_time


    def modified_time(self, name):
        """
        Returns the last modified time (as datetime object) of the file
        specified by name.
        """
        return FileUpload.objects.get(name=name).modified_time


    def exists(self, name):
        """
        Returns True if a file referenced by the given name already exists in the
        storage system, or False if the name is available for a new file.
        """
        return FileUpload.objects.filter(name=name).exists()


    def delete(self, name):
        """
        Deletes the specified file from the storage system.
        """
        FileUpload.objects.get(name=name).delete()


    def _open(self, name, mode='rb'):
        """
        Retrieves the specified file from storage.
        """
        try:
            fobj = FileUpload.objects.get(name=name)
            fobj.save()
        except FileUpload.DoesNotExist:
            return None
        inMemFile = BytesIO(fobj.data)
        inMemFile.name = fobj.name
        inMemFile.mode = mode
        retFile = File(inMemFile)
        return retFile


    def _save(self, name, content):
        """
        Saves new content to the file specified by name. The content should be
        a proper File object or any python file-like object, ready to be read
        from the beginning.
        """
        fobj, _ = FileUpload.objects.get_or_create(name=name)
        fobj.data = content.read()
        fobj.size = len(fobj.data)
        fobj.modified_time = datetime.now()
        fobj.save()
        return name
