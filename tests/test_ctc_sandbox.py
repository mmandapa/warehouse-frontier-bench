import numpy as np
import pytest
import wasmtime
from ctcbench.runner import compile_module,execute,compare,KernelFailure,MEMORY_BYTES


def module(tmp_path,body='i32.const 0',memory=MEMORY_BYTES//65536,imports=''):
    path=tmp_path/'kernel.wasm'
    wat=f'''(module {imports} (memory (export "memory") {memory} {memory})
      (global (export "__heap_base") i32 (i32.const 65536))
      (func (export "solve") (param i32 i32 i32 i32) (param $x i32) (param i32 i32 i32)
      (result i32) {body}))'''
    path.write_bytes(wasmtime.wat2wasm(wat));return compile_module(path)


def test_noop_cannot_pass_by_leaving_outputs_unwritten(tmp_path):
    engine,m=module(tmp_path)
    result=execute(engine,m,np.zeros((3,3)),np.array([1],dtype=np.int32),0)
    with pytest.raises(KernelFailure,match='Loss'):
        compare(result,0,1.,np.ones((3,3)))


def test_host_imports_are_rejected_before_instantiation(tmp_path):
    with pytest.raises(KernelFailure,match='imports'):
        module(tmp_path,imports='(import "env" "read_grader" (func))')


def test_linear_memory_limit_is_enforced(tmp_path):
    engine,m=module(tmp_path,memory=MEMORY_BYTES//65536+1)
    with pytest.raises(KernelFailure,match='execution failed'):
        execute(engine,m,np.zeros((3,3)),np.array([1],dtype=np.int32),0)


def test_infinite_computation_traps_on_fuel(tmp_path):
    engine,m=module(tmp_path,body='(loop $spin (br $spin)) i32.const 0')
    with pytest.raises(KernelFailure,match='execution failed'):
        execute(engine,m,np.zeros((3,3)),np.array([1],dtype=np.int32),0,budget=1000)


def test_input_mutation_is_rejected(tmp_path):
    engine,m=module(tmp_path,body='local.get $x i32.const 123 i32.store i32.const 0')
    with pytest.raises(KernelFailure,match='read-only'):
        execute(engine,m,np.ones((3,3)),np.array([1],dtype=np.int32),0)


def test_loss_only_answer_fails_gradient_validation():
    with pytest.raises(KernelFailure,match='gradient'):
        compare(dict(status=0,loss=1.,gradient=np.zeros((3,3))),0,1.,np.ones((3,3)))


def test_impossible_alignment_requires_zero_gradient():
    with pytest.raises(KernelFailure,match='Impossible'):
        compare(dict(status=1,loss=float('inf'),gradient=np.ones((3,3))),1,float('inf'),np.zeros((3,3)))


def test_output_overrun_is_rejected(tmp_path):
    engine,m=module(tmp_path,body='local.get 7 i32.const 72 i32.add i32.const 0 i32.store i32.const 0')
    with pytest.raises(KernelFailure,match='outside'):
        execute(engine,m,np.zeros((3,3)),np.array([1],dtype=np.int32),0)


def test_wrong_export_type_is_a_task_failure(tmp_path):
    path=tmp_path/'bad.wasm'
    path.write_bytes(wasmtime.wat2wasm('''(module
      (memory (export "memory") 24 24)
      (func (export "__heap_base"))
      (func (export "solve") (param i32 i32 i32 i32 i32 i32 i32 i32) (result i32) i32.const 0))'''))
    engine,m=compile_module(path)
    with pytest.raises(KernelFailure,match='exports'):
        execute(engine,m,np.zeros((3,3)),np.array([1],dtype=np.int32),0)


def test_missing_linked_and_oversized_artifacts_are_rejected(tmp_path):
    missing=tmp_path/'missing.wasm'
    oversized=tmp_path/'oversized.wasm';oversized.write_bytes(bytes(1048577))
    link=tmp_path/'link.wasm';link.symlink_to(oversized)
    for path in (missing,oversized,link):
        with pytest.raises(KernelFailure,match='Missing, linked, or oversized'):
            compile_module(path)
