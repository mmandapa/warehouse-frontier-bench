"""Run an untrusted numerical module with no host imports, filesystem, clock, or network."""
import struct
import time
from pathlib import Path
import numpy as np
import wasmtime

MEMORY_BYTES=1536*1024
MAX_MODULE_BYTES=1024*1024


class KernelFailure(ValueError):pass


def fuel_budget(T,C,U):
    return 50_000_000+6000*T*(2*U+1)+4000*T*C


def compile_module(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or not 8<=path.stat().st_size<=MAX_MODULE_BYTES:
        raise KernelFailure('Missing, linked, or oversized kernel.wasm')
    config=wasmtime.Config();config.consume_fuel=True
    engine=wasmtime.Engine(config)
    try: module=wasmtime.Module(engine,path.read_bytes())
    except wasmtime.WasmtimeError as exc:raise KernelFailure('Invalid WebAssembly module') from exc
    if module.imports:raise KernelFailure('Module imports are forbidden; no WASI or host callbacks are supplied')
    return engine,module


def execute(engine,module,logits,target,blank,budget=None):
    T,C=logits.shape;U=len(target)
    store=wasmtime.Store(engine)
    store.set_limits(memory_size=MEMORY_BYTES,instances=1,memories=1,tables=1,table_elements=1024)
    initial=fuel_budget(T,C,U) if budget is None else budget
    store.set_fuel(initial)
    start=time.monotonic()
    try:
        instance=wasmtime.Instance(store,module,[]);exports=instance.exports(store)
        memory=exports['memory'];solve=exports['solve'];heap_global=exports['__heap_base']
        if not isinstance(memory,wasmtime.Memory) or not isinstance(solve,wasmtime.Func) or not isinstance(heap_global,wasmtime.Global):
            raise KernelFailure('Expected memory, solve function, and __heap_base global exports')
        if str(heap_global.type(store).content)!='i32':
            raise KernelFailure('__heap_base must have type i32')
        heap=heap_global.value(store)
        signature=solve.type(store)
        if [str(t) for t in signature.params]!=['i32']*8 or [str(t) for t in signature.results]!=['i32']:
            raise KernelFailure('solve must take eight i32 arguments and return one i32')
        if type(heap) is not int or not 65536<=heap<MEMORY_BYTES:
            raise KernelFailure('__heap_base must be an i32 global at or above 65536')
        guard=bytes(range(64)); input_bytes=np.asarray(logits,dtype='<f8').tobytes()
        target_bytes=np.asarray(target,dtype='<i4').tobytes()
        p=(heap+64+7)&~7
        xptr=p;p+=len(input_bytes);g1=p;p+=64
        yptr=(p+7)&~7;p=yptr+len(target_bytes);g2=p;p+=64
        lptr=(p+7)&~7;p=lptr+8
        gptr=p;p+=len(input_bytes);g3=p;p+=64
        if p>memory.data_len(store):raise KernelFailure('Module static/stack storage leaves insufficient space for the specified I/O buffers')
        memory.write(store,input_bytes,xptr);memory.write(store,target_bytes,yptr)
        for address in (xptr-64,g1,g2,g3):memory.write(store,guard,address)
        memory.write(store,struct.pack('<d',float('nan')),lptr)
        memory.write(store,np.full((T,C),np.nan,dtype='<f8').tobytes(),gptr)
        status=solve(store,T,C,U,int(blank),xptr,yptr,lptr,gptr)
        if bytes(memory.read(store,xptr,xptr+len(input_bytes)))!=input_bytes or bytes(memory.read(store,yptr,yptr+len(target_bytes)))!=target_bytes:
            raise KernelFailure('Kernel modified read-only input buffers')
        if any(bytes(memory.read(store,a,a+64))!=guard for a in (xptr-64,g1,g2,g3)):
            raise KernelFailure('Kernel wrote outside an output buffer')
        loss=struct.unpack('<d',bytes(memory.read(store,lptr,lptr+8)))[0]
        grad=np.frombuffer(memory.read(store,gptr,gptr+len(input_bytes)),dtype='<f8').reshape(T,C).copy()
        return dict(status=status,loss=loss,gradient=grad,fuel_used=initial-store.get_fuel(),seconds=time.monotonic()-start)
    except KernelFailure:raise
    except (wasmtime.Trap,wasmtime.WasmtimeError,KeyError,TypeError,IndexError) as exc:
        raise KernelFailure(f'WebAssembly execution failed: {type(exc).__name__}: {str(exc)[:200]}') from exc


def compare(result,status,loss,gradient):
    if result['status']!=status:raise KernelFailure(f'Expected status {status}, got {result["status"]}')
    if status==1:
        if not np.isposinf(result['loss']) or np.any(result['gradient']!=0):
            raise KernelFailure('Impossible alignment needs +infinity loss and zero gradient')
        return
    if not np.isfinite(result['loss']) or not np.isclose(result['loss'],loss,atol=1e-6,rtol=1e-8):
        raise KernelFailure('Loss differs from the independent reference')
    if not np.isfinite(result['gradient']).all() or not np.allclose(result['gradient'],gradient,atol=2e-6,rtol=2e-5):
        difference=float(np.nanmax(np.abs(result['gradient']-gradient)))
        raise KernelFailure(f'Logit gradient differs from the independent reference (max absolute error {difference:.6g})')
