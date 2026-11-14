from client import BayClient


def main():
    bay = BayClient()
    sequences = bay.forecast_commands()
    bay.submit([(0.0, 0.0, 0.0)] * len(sequences))


if __name__ == "__main__":
    main()
