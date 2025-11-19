import argparse
from combined import SupplementTripleExtractor

def main():
    parser = argparse.ArgumentParser(description='Advanced Medical Triple Extraction - Modular')
    parser.add_argument('--input', default='knowledge_graph/data/standardized_rows.csv')
    parser.add_argument('--output-dir', default='knowledge_graph/data')
    args = parser.parse_args()

    e = SupplementTripleExtractor(args.input, args.output_dir)
    print("Starting extraction...")
    e.process()
    print(f"Extraction complete! Files saved to {args.output_dir}")
    return 0

if __name__ == "__main__":
    exit(main())
