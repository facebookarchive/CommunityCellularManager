#if PY_VERSION_HEX >= 0x03000000
#define SWIG_init PyInit__freeswitch
PyObject* SWIG_init(void);
#else
#define SWIG_init init_freeswitch
#define PyUnicode_AsUTF8            PyString_AsString
void SWIG_init(void);
#endif
