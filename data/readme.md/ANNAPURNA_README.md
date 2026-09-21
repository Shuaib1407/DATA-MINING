

billing\_notes(5).md

File

masters(5).sql

File

Finance Monthly(5)



Annapurna stores runs 12 supermarkets. Every night , each store’s billing system writes out that day’s sales lines to a shared folder . Hand office has no data team; an analyst opens the files in a spreadsheet, one month at a time and types the totals into a slide.

Last week the CFO asked for october revenue and was given three different figures by three different people, all working form the same folder . In the same meetings the category manager asked what a particular biscuit pack sold for in march and the spreadsheet answers with the price on the shelf today.

The CEO’s instruction to you , in full:



“Build me something where October is October . i want to slice revenue by store , by product category . by day of the week and by ,month and i want the same number every time I ask . i also ant last March’s prices when i ask about last March . I do not care what software you use . I do care that the analyst can stop opening files by hand”.



What you are given in exam/data/



Sales - roughly six hundred daily files , one per store per ady . Mixed CSV and parquet.Columns include the bill number, the product code , quantity , unit price , a line type and a timestamp.

Masters.sql- to be loaded into PostgreSQl: stores , products,product6 categories , and a table of price revisions with the date eacj took effect.

Finance\_monthly.csv– the twelve monthly revenue figures the finance team has already closed and signed off. This is your reconciliation target for part(f).\\

Billing\_notes.md – whatever the billing vendor left behind. Read it . it is short and it matters.



Tasks:



Stand the platform up and land the data . bring up an object store , a relational database and an analytical query engine . load the daily files into the object store , organised so that a query about one store in one month does not have to look at the other eleven months. Say what organisation you chose , then show it working : for one such query , how many files and how many bytes could the engine possibly have to openunder your layout,compared with putting everything in one folder?

Make it safe to run twice. Some days appear in the folder more than once – the billing system re-sends when a store reports a problem . build the loading step so that running it three times in a row gives the same result as running it once . prove it : run it three times, record the row count and a checksu, after each run and include the output.



c) design the tables behind the dash board : the dash board must slice revenue by store by the product category ; by day of the week and by month , quickly  . design and build the tables that make the possible without  repeating each stores name and address on every on millions of the sales lines . note two things about source data before you start not every line is a sales , and the product code that was retired has since ben reissued to a different product so the code alone dose not identify what was sold



d)Make March use march's prices. price CHANGE. USING  THE revision table arrange things so that a report for march 2024 uses the prices that applied in march 2024 while a report for last month uses last months from the same query with no change to the code between the two demonstrate by running one query twice, differing only in the reporting period.



e)Query across the two systems. the sales data is the object store; the stores, products and categories are in PostgreSQL. write one query that joins both without first copying either side into the others. then tell us using evidence from the engine rather than from documentation, which parts of that query were evaluated where.



f)Reconcile. compare your monthly revenue against finance\_monthly.csv.you will not match every month that differs, say whether the cause is something wrong with the source data, a different in how the two of you define revenue, or a bug in your pipeline-and say which of the three you would take back to the finance team.



one warning.it is easy to produce an October figure that is roughly twice the correct one. If your revenue looks surprisingly healthy part(c)is where to look before you submit 



Pasted text(9).txt

Document

Pasted text (2).txt

Document

i want the eminio to be like this

that command is running each stores

Pasted text(10).txt

Document

C:\\Users\\Shuaib Ahmed\\OneDrive\\Documents\\data\_2\\data>dir sales /b | find /c /v ""

4457



C:\\Users\\Shuaib Ahmed\\OneDrive\\Documents\\data\_2\\data>

is this right the pervsion one



C:\\Users\\Shuaib Ahmed\\OneDrive\\Documents\\data\_2\\data>dir raw\\year=2024\\month=10 /ad

The system cannot find the file specified.



C:\\Users\\Shuaib Ahmed\\OneDrive\\Documents\\data\_2\\data>

Pasted text(20260919-162736).txt

Document

here what to select

which screenshot should i put

name

screenshot name



Sure — you want the README to be theory only, without all the SQL commands, screenshot commands, or technical command details.



Here is a clean theory version:



Annapurna Supermarket Data Platform

1\. Introduction



Annapurna is a chain of 12 supermarkets. Every night, each store's billing system generates sales files containing the day's transactions.



Originally, the company depended on an analyst manually opening files, calculating monthly revenue, and entering the results into presentation slides. This created inconsistent results because different people could calculate the same month differently.



The CEO therefore required a system that would provide consistent revenue figures, allow analysis by different business dimensions, preserve historical prices, and eliminate manual file processing.



2\. Problem Statement



The main problems were:



Sales data was stored in many daily files.

Files came from different stores and in different formats.

Billing systems sometimes resent files.

Duplicate transactions could therefore occur.

Product codes could be reused for different products.

Current product prices could not be safely used for historical reports.

Not every billing line represented revenue.

One store had a known three-day source-data gap.

Finance had signed-off monthly revenue figures that needed reconciliation.

Analysts had to manually open files to answer business questions.



The objective was to build a reliable data platform that solves these problems.



3\. Technology Stack



The platform uses three main technologies.



MinIO



MinIO is used as the object-storage layer. Raw sales files and curated Parquet data are stored here.



PostgreSQL



PostgreSQL stores relational master data such as:



Stores

Products

Product categories

Price revisions

DuckDB



DuckDB is used as the analytical query engine. It can read Parquet files from MinIO and access PostgreSQL tables in the same analytical query.



Docker is used to run the MinIO and PostgreSQL services.



4\. Data Organization



The raw sales data is organized by:



Year → Month → Store



For example:



raw/

&#x20; year=2024/

&#x20;   month=10/

&#x20;     store=S01/



This partitioning prevents a query for one store and month from having to inspect unrelated stores and months.



The dataset contained 4,457 sales files across the 12 stores.



The raw data was preserved rather than deleting duplicate or resend files.



5\. Data Normalization



The stores did not all produce files in exactly the same format.



Different stores used different:



Delimiters

Column names

Column orders

Timestamp formats



The data was therefore converted into a common structure containing fields such as:



Store

Business date

Bill number

Line number

Product code

Quantity

Unit price

Line type

Timestamp

Source file



This created a consistent structure for downstream processing.



6\. Duplicate and Resend Handling



The billing system sometimes resends files when a problem occurs.



Therefore, duplicate files were not simply deleted from the raw layer.



The business key used for individual sales lines was:



Bill number + Line number



Duplicate business keys were identified during processing.



The system also checked whether duplicate records contained conflicting information. No conflicting duplicate records were found in the supplied data.



The cleaned dataset contained 1,120,924 rows.



The loading process was also tested repeatedly using row counts and checksums to demonstrate that rerunning the process does not continually create additional duplicate records.



7\. Revenue Definition



Not every billing record represents revenue.



The vendor rules were used to determine how each line type should be handled.



SALE — contributes revenue.

RETURN — reduces revenue.

DISCOUNT — reduces revenue.

VOID — represents cancellation and must be handled consistently.

TAX — is not treated as revenue.

TENDER — is not treated as revenue because it represents the bill payment/total and could cause double counting.



This ensures that revenue calculations follow a consistent business definition.



8\. Star Schema



A star-schema structure was created for analytical reporting.



The dimensions include:



Store

Product category

Product

Date



The central fact table contains the measurable sales information and revenue.



The final model contained:



12 stores

14 categories

1,224 products

366 dates

757,246 fact rows



This structure allows revenue to be analyzed by:



Store

Product category

Day of week

Month



without repeatedly storing descriptive information such as store names and category names on every sales record.



9\. Product Code Reuse



An important data-quality issue was that product codes were reused during the year.



Therefore, a product code by itself was not enough to identify the product.



The product was matched using:



Product code + business date



The business date was checked against the product's validity period.



This prevents a historical transaction from being incorrectly associated with a different product that later reused the same product code.



10\. Historical Pricing



Historical prices were handled using the price-revision table in PostgreSQL.



Each price revision has an effective period.



When a report is generated for a particular date, the system selects the price revision that was valid during that period.



For example, the same product had:



March 2024 price: ₹1,140.00

October 2024 price: ₹1,203.94



Therefore, a March report does not incorrectly display the October or current price.



11\. Cross-System Analytics



One of the important requirements was to combine information stored in different systems.



Sales data is stored as Parquet files in MinIO, while master data is stored in PostgreSQL.



DuckDB was used to query both systems together.



The engine evidence showed:



READ\_PARQUET for MinIO sales data.

POSTGRES\_SCAN for PostgreSQL tables.

Hash joins for combining the data.

Aggregation for calculating revenue.



This means the systems did not need to be manually copied into one another before analysis.



12\. Finance Reconciliation



The calculated monthly revenue was compared with Finance's signed-off monthly revenue.



The comparison showed differences between the two sources.



For example, October had:



Finance revenue: ₹56,359,195.92

Pipeline revenue: ₹56,927,219.51

Difference: ₹568,023.59



The differences were investigated rather than simply declaring one number correct.



13\. S07 July Data Gap



The vendor notes identified a known source-data problem for Store S07.



Three days of July 2024 were missing:



9 July

10 July

11 July



The data loaded into the platform confirmed that these dates were absent.



This is classified as a source-data issue, rather than silently treating the missing records as zero revenue.



The appropriate action is to reconcile these missing dates with the phone-in figures maintained by Finance.



14\. Final Outcome



The Annapurna platform replaces the manual spreadsheet-based process with a repeatable data pipeline.



The final architecture provides:



Centralized raw data storage.

Partitioned sales data.

Duplicate and resend handling.

Standardized sales data.

Consistent revenue rules.

A star schema for analytics.

Historical product identification.

Historical price reporting.

Cross-system querying.

Finance reconciliation.

Identification of source-data gaps.



The analyst no longer needs to manually open hundreds or thousands of files to answer routine revenue questions.



The platform provides a consistent foundation for questions such as:



What was October revenue?

What was revenue by store?

What was revenue by category?

Which day of the week generated the most revenue?

What was a product's price in March?

Why does pipeline revenue differ from Finance's figure?

Conclusion



The Annapurna data platform transforms a manual and inconsistent reporting process into a structured, reproducible analytical system using MinIO, PostgreSQL, and DuckDB.



It preserves the original data, handles duplicate billing resends, applies consistent business rules, supports historical analysis, combines data across systems, and provides a clear reconciliation process with Finance.



in the readme



Done. I changed the README to be theory-only—no SQL commands or command-by-command instructions.



It now explains:



The question/problem statement

Objectives

Architecture

What we did in each of the 6 tasks

Partitioning

Deduplication and idempotency

Star schema

Product-code reuse

Revenue rules

Historical pricing

MinIO + PostgreSQL + DuckDB cross-system querying

Finance reconciliation

Final results and conclusion



Download the theory-only ANNAPURNA\_README.md 



ANNAPURNA\_README.md

Document

command



If you mean the Windows command to create/open the README file, use:



Create README File

notepad ANNAPURNA\_README.md



If you want to create it directly from CMD without opening Notepad:



Create Empty README

type nul > ANNAPURNA\_README.md



Then you can open it with:



notepad ANNAPURNA\_README.md



ANNAPURNA\_README.md

Annapurna Supermarket Data Platform

Project Overview



Annapurna operates 12 supermarkets. Every night, each store's billing system produces sales files containing transaction lines. The original process required an analyst to manually open files month by month, calculate totals, and enter the results into presentation slides.



This caused inconsistent reporting. The main business requirement was to build a reliable data platform so that the same question produces the same result every time, historical information remains historically correct, and analysts no longer need to manually open sales files.



The platform was designed using MinIO, PostgreSQL, DuckDB, and Docker.



Problem Statement



The CEO required a system that could:



Provide a consistent monthly revenue figure.

Slice revenue by store.

Slice revenue by product category.

Slice revenue by day of week.

Slice revenue by month.

Handle duplicate or resent billing files safely.

Preserve historical product and pricing information.

Allow historical prices to be retrieved for the correct reporting period.

Combine sales stored in object storage with master data stored in PostgreSQL.

Reconcile calculated revenue against Finance's signed-off figures.

Remove the need for analysts to manually open files and calculate totals.

Solution



The solution is a small analytical data platform.



MinIO is used as the object store for sales files. PostgreSQL stores master data such as stores, products, categories, and price revisions. DuckDB acts as the analytical query engine and performs data normalization, cleaning, transformations, joins, aggregations, and cross-system queries.



The overall flow is:



Daily Sales Files

&#x20;      |

&#x20;      v

&#x20;    MinIO

&#x20;      |

&#x20;      v

&#x20;    DuckDB

&#x20;      |

&#x20;      +----> Normalize

&#x20;      |

&#x20;      +----> Deduplicate

&#x20;      |

&#x20;      +----> Curated Parquet

&#x20;      |

&#x20;      +----> Analytical Fact Table

&#x20;      |

&#x20;      v

Dashboard / Reporting



PostgreSQL

&#x20;  |

&#x20;  +---- Stores

&#x20;  +---- Products

&#x20;  +---- Categories

&#x20;  +---- Price Revisions

Task 1 — Data Landing and Partitioning



The raw sales files were stored in MinIO.



The data was organized using year, month, and store partitions:



raw/

└── year=2024/

&#x20;   └── month=10/

&#x20;       └── store=S01/



This organization allows the analytical engine to target only the relevant partition when a query asks for a particular store and month.



The raw source data was preserved rather than deleting or modifying the original files.



The dataset contained 4,457 CSV files.



The partitioning approach reduces unnecessary file inspection compared with placing all files in a single directory.



Task 2 — Duplicate and Resend Handling



The billing system can resend files when there is a problem. A resend may contain the same transactions as the original file, and some resend files can be incomplete.



Therefore, duplicate handling was performed at the transaction-line level instead of simply deleting resend files.



The business key used was:



bill\_no + line\_no



Duplicate business keys were identified and checked for conflicting values.



The raw files remained available in MinIO, while the cleaning process produced a deduplicated analytical dataset.



Idempotency was verified by running the cleaning process again and comparing:



Row count

Checksum



The repeated processing produced the same result, demonstrating that rerunning the process does not continually create additional duplicate records.



Task 3 — Analytical Star Schema



A dimensional model was created for analytical reporting.



The main dimensions were:



Store dimension

Category dimension

Product dimension

Date dimension



The fact table stores measurable sales information such as quantity and revenue.



The dimensions contain descriptive information, so store names, category names, and other descriptive attributes do not have to be repeated unnecessarily on every sales transaction.



The model supports analysis by:



Store

Product category

Day of week

Month



The final model contained:



12 stores

14 categories

1,224 products

366 dates

757,246 fact rows

Product Code Reuse



A product code was not treated as a permanent identifier for a product because the source notes stated that product codes could be retired and later reused.



Therefore, product matching used both:



product\_code

business\_date



and the product's validity period:



valid\_from

valid\_to



This prevents a historical transaction from being incorrectly associated with a different product that reused the same code later.



Revenue Definition



Not every billing line represents revenue.



The implemented business rules were:



SALE contributes positive revenue.

RETURN reduces revenue.

DISCOUNT reduces revenue.

VOID represents cancellation and is handled consistently.

TAX is not counted as revenue.

TENDER is not counted as revenue because it represents the bill total and would otherwise cause double counting.



These rules were applied when constructing the analytical fact table.



Task 4 — Historical Prices



Historical prices were handled using the PostgreSQL price revision table.



A price revision has an effective period, allowing the system to determine which selling price was valid for a particular reporting date.



The same query logic can therefore be used for different reporting periods.



For example, the tested product had one price in March 2024 and a different price in October 2024.



This solves the problem where a historical report might otherwise display the current shelf price instead of the price applicable during the historical reporting period.



Task 5 — Cross-System Query



The sales data is stored as Parquet files in MinIO, while master data is stored in PostgreSQL.



DuckDB was used to query both systems together.



A single query was able to:



Read sales directly from MinIO.

Read stores from PostgreSQL.

Read products from PostgreSQL.

Read product categories from PostgreSQL.

Join the datasets.

Calculate revenue.

Aggregate the result by store and category.



The query produced 168 store-category combinations.



The DuckDB EXPLAIN plan provided direct engine evidence showing:



READ\_PARQUET



for the MinIO sales data and:



POSTGRES\_SCAN



for the PostgreSQL master tables.



DuckDB then performed the joins and aggregation.



This demonstrated that the two systems could be queried together without copying the data from one system into the other.



Task 6 — Finance Reconciliation



Finance provided a monthly file containing signed-off revenue figures for 2024.



The pipeline calculated monthly revenue from the analytical fact table and compared it with the Finance figures.



The comparison showed differences between the two sources.



The differences were investigated rather than simply declaring one number correct.



The vendor notes identified a known source-data issue for S07 in July 2024. The S07 data contained 28 July dates instead of all 31 dates, with the following dates absent:



2024-07-09

2024-07-10

2024-07-11



This was treated as a source-data completeness issue. The missing revenue was not artificially invented from nearby dates.



The reconciliation therefore distinguishes between:



Source-data gaps.

Revenue-definition differences.

Actual pipeline problems.



The duplicate validation and repeated-load checks provided evidence that the differences were not caused by uncontrolled duplicate ingestion.



Final Platform



The completed platform provides a repeatable process:



Raw Files

&#x20;  |

&#x20;  v

MinIO Object Storage

&#x20;  |

&#x20;  v

Partitioned Raw Data

&#x20;  |

&#x20;  v

DuckDB Normalization

&#x20;  |

&#x20;  v

Duplicate Handling

&#x20;  |

&#x20;  v

Curated Parquet

&#x20;  |

&#x20;  v

Star Schema

&#x20;  |

&#x20;  v

Analytical Queries

&#x20;  |

&#x20;  +---- Store

&#x20;  +---- Category

&#x20;  +---- Weekday

&#x20;  +---- Month

&#x20;  |

&#x20;  v

Finance Reconciliation



The main purpose of the platform is to replace manual spreadsheet processing with a consistent and reproducible data workflow.



Final Verification



The final platform verification showed:



clean\_sales   = 1,120,924

fact\_sales    =   757,246

dim\_store     =        12

dim\_category  =        14

dim\_product   =     1,224

dim\_date      =       366



These checks confirm that the main analytical components were created successfully.



Conclusion



The Annapurna data platform addresses the original business problem by creating a structured and repeatable pipeline from raw billing files to analytical reporting.



The platform preserves raw data, handles billing resends, applies defined revenue rules, handles historical product identities and prices, supports cross-system queries, and provides a reconciliation process against Finance.



As a result, analysts can query the data directly instead of manually opening files and calculating monthly figures.

