#!/usr/bin/python

'''
Struct Map List
LTaoist

Struct Map List map the C binary file into python list, and
each item you can access as a python dict.
'''

from struct import Struct
import os

cook_string =[
            lambda x: x[:x.find('\x00')],
            lambda x: x
            ]

cook_array = [
            lambda x: x[:x.find('\x00')],
            lambda x: ' '.join(x)
            ]

cook_gb_unicode = [
            lambda x: x[:x.find('\x00')].decode(encoding='GB18030',errors='ignore'),
            lambda x: x.encode('GB18030')
            ]

class Cook :
    '''
    this is only provide you a set of tools to do with 
    the binary data
    '''
    def __init__(self):
        self.cook_er = {}
        self.cook_er["string"] = [
            lambda x: x[:x.find('\x00')],
            lambda x: x
            ]
        self.cook_er["array"] = [
            lambda x: x[:x.find('\x00')],
            lambda x: ' '.join(x)
            ]
        self.cook_er["gb_unicode"] = [
            lambda x: x[:x.find('\x00')].decode(encoding='GB18030',errors='ignore'),
            lambda x: x.encode('GB18030')
            ]
        self.cook_er["number"] = [
            lambda x : x
            ]
    def get_cook_tools(self,kind):
        return self.cook_er[kind]

def _tidy_fields_list(fields_list):
    fields = []
    handlers = {}
    rebuilders = {}
    for item in fields_list:
        if isinstance(item, tuple):
            fields.append(item[0])
            handlers[item[0]] = item[1][0]
            rebuilders[item[0]] = item[1][1]
        else:
            fields.append(item)
    return tuple(fields), handlers, rebuilders

class SMList:

    '''
    Struct Map List map the C binaray file into python list, and you can
    access each item as python dict.

    Suppose that file `user.data` formed by c struct :

        struct user {
            char userid[20];
            unsigned int id;
        }

    You can acces it as follow:
        userdata = SMList.new('user.data', '20sI',
                              ['userid', 'id'])
        print userdata[0] # it is just a dict
        print userdata[-1] # it is ok too!
        print userdata.count() # or len(userdata)
        for user in userdata :
            print user

    It is ok to open a big file due to access is lazy.

    '''

    def __init__(self, filename, fmter, fields, handlers, rebuilders):
        '''
        It's recommend to use the classmethod `SMList.new`,
        Don't use this function unless you know how it works.
        '''
        self._filename = filename
        self._file = open(filename, 'r+b')
        self._fmter = fmter
        self._size = self._fmter.size
        self._fields = fields
        self._handlers = handlers
        self._rebuilders = rebuilders

    @classmethod
    def new(cls, filename, fmter, fields_list):
        '''
        Build a new smlist.

        `filename` is the name of the file which will be handler,

        `fmter` decleare the data struct and type of the c struct,
        it is as same as the fmt in `struct.unpack` function :
          <http://docs.python.org/2/library/struct.html#format-strings>
        `fmter` must be a string.

        `fields_list` decleare the key to access the struct in python,
        it is should be a list as follow:
            [
                field1,
                field2,
                ...
            ]
        and you can access the dict by data[fields1], data[fiedlsd2] ...
        It is also possible to add a handler of the fields:
            [
                ...
                (field1, handler)
                ...
            ]
        The handler should be two callable object both like
        lambda x: express(x) . The first one cook the raw
        data and return it as the real value. The second one
        dump the real value into raw_data so that you can
        save the data safely.
        eg.
            [
                ('userid', cook_string),
                'id',
            ]

        cook_string will remove the string after '\x00'.
        cook_array will remove the string after '\x00',
          and split them by ' ' .
        cook_gb_unicode will remove the string after '\x00'
          and decode them by 'GB18030'
        
        '''
        return cls(filename, Struct(fmter),
                   *_tidy_fields_list(fields_list))

    def get_uncook(self, key):
        '''Return the raw data without handling.'''
        self._file.seek(key * self._size)
        raw = self._file.read(self._size)
        if raw == '':
            raise ValueError('Overflow index.')
        return self._fmter.unpack(raw)

    def get(self, key):
        '''Return the key-th data from file.'''
        if key < 0:
            key += self.count()
        return self._wrapper(self.get_uncook(key))

    def save(self, key, value):
        pass

    def find_left(self, checker, start=-1):
        if start < 0 :
            start += self.count()
        while start >= 0:
            if checker(self.get(start)) :
                return start
            start += 1

    def find_right(self, checker, start=0):
        total = self.count()
        if start < 0 :
            start += total
        while start < total:
            if checker(self.get(start)):
                return start
            start -= 1

    def _wrapper(self, raw):
        res = dict(zip(self._fields, raw))
        if self._handlers:
            for field in self._handlers:
                res[field] = self._handlers[field](res[field])
        return res

    def add_handler(self, field, cook):
        '''Add/Set a handler of a field.'''
        self._handlers[field] = cook[0]
        self._rebuilders[field] = cook[1]

    def count(self):
        '''Return total object in the file.'''
        return os.path.getsize(self._filename) // self._size

    def iter(self, start, stop, step):
        '''Get a iterator.'''
        while start < stop:
            yield self.get(start)
            start += step

    def __len__(self):
        return self.count()

    def __getitem__(self, item):
        if isinstance(item, slice):
            return self.iter(item.start, item.stop, item.step or 1)
        else:
            return self.get(item)

    def __iter__(self):
        total = self.count()
        return self.iter(0, total, 1)

class SMListFactory:

    '''
    The Factory Class to make many SMList of same fmt and fields.
    Usage:
        f = SMListFactory(fmt, fiedls)
        f1 = f.connect('f1.data')
        print f1[3]
        f2 = f.connect('f2.data')
        print f2[5]
    '''

    def __init__(self, fmt, fields):
        self._fmter = Struct(fmt)
        self._fields, self._handlers, self._rebuilders = \
            _tidy_fields_list(fields)        

    def connect(self, filename):
        return SMList(filename, self._fmter, self._fields,
                      self._handlers, self._rebuilders)
