bengsoon/volve_daily_drilling_report - hugging face
There is also an Alpaca-format conversion of the same 1,759 reports, useful for NLP experimentation.
Volve also gives you real-time drilling data

AndrzejTunkiel
/
VolveDataExploration--{VolveDataExploration
This repository contains source code for methods mentioned in the OMAE2020-18151 paper titled Drilling Dataset Exploration, Visualization, Processing and Interpretation Using Volve Field Data. Paper is currently accepted, but not published.

Code
Code is provided as Jupyter Notebook

Find attributes, plot charts
This notebook allows one to:

Search all logs for a given attribute
Generate charts as PNG files for given attribute
Data for exploration
Equinor released Volve dataset without any preprocessing. This makes working with real-time data difficult. This initiated an effort to convert WITSML files into CSV files, which are considered a basic standard in Data Science.

Pre-processed real-time drilling dataset, originally provided as WITSML files as a part of Equinor's Volve dataset, is available at webpages of University of Stavanger at http://www.ux.uis.no/~atunkiel/.

All code is provided as-is under Creative Commons (CC BY-NC-SA 4.0) license.}





30. But there is a big dataset problem

This is something you should tell the team honestly.

Public data does not necessarily give you exactly the labels you want for:

stuck pipe
mud loss
precursor
intervention
outcome

in a clean supervised-learning format.

The public Volve dataset gives you rich operational data, but you will likely have to derive/annotate the event labels from reports and sensor behavior.

Therefore your dataset strategy should be:

                 DATA
                  │
        ┌─────────┴─────────┐
        │                   │
   PUBLIC REAL DATA      SYNTHETIC
        │                   │
      Volve          controlled scenarios
        │                   │
        └─────────┬─────────┘
                  │
             PROTOTYPE