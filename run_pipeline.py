"""Run the whole pipeline: clean the raw CSV, then load it into MySQL.

    python run_pipeline.py
"""

from src import cleaning, load_to_mysql

if __name__ == "__main__":
    print("== Step 1/2: cleaning & preprocessing")
    result = cleaning.clean()
    cleaning.save(result)
    r = result["report"]
    print(f"   {r['raw_shape'][0]:,} raw rows -> {r['fact_rows']:,} clean records "
          f"({r['countries']} countries, {r['indicators']} indicators)")
    print("== Step 2/2: loading into MySQL")
    load_to_mysql.main()
    print("\nAll done. Start the dashboard with:  streamlit run app.py")
