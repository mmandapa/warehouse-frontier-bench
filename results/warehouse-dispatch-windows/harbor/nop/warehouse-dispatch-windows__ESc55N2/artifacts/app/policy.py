from client import Dispatch


if __name__ == '__main__':
    dispatch = Dispatch()
    while 'result' not in dispatch.observe():
        dispatch.step({})
