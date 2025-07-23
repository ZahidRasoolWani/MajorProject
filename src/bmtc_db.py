import pandas as pd
import sqlite3
import os
from datetime import datetime

def create_bmtc_database():
    """
    Create optimized SQLite database from BMTC CSV files in current directory
    """
    print("🚀 Creating BMTC SQLite Database from current directory...")
    
    # Use current directory
    csv_folder = os.getcwd()
    print(f"📂 Working directory: {csv_folder}")
    
    db_path = 'bmtc_routes.db'
    
    # Remove existing database
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"🗑️  Removed existing {db_path}")
    
    # Connect to SQLite
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Enable WAL mode for better performance
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA cache_size=10000;")
    cursor.execute("PRAGMA temp_store=MEMORY;")
    
    # Your CSV files (from the ls command you showed)
    csv_files = {
        'agency': 'agency.csv',
        'calendar': 'calendar.csv', 
        'fare_attributes': 'fare_attributes.csv',
        'fare_rules': 'fare_rules.csv',
        'feed_info': 'feed_info.csv',
        'routes': 'routes.csv',
        'shapes': 'shapes.csv',
        'stops': 'stops.csv',
        'stop_times': 'stop_times.csv',
        'translations': 'translations.csv',
        'trips': 'trips.csv'
    }
    
    stats = {}
    
    # First, let's see what files actually exist
    print("\n📋 Checking available files:")
    existing_files = os.listdir('.')
    for file in existing_files:
        if file.endswith('.csv'):
            print(f"   ✅ Found: {file}")
    
    print("\n📊 Processing files...")
    
    for table_name, csv_file in csv_files.items():
        if os.path.exists(csv_file):
            print(f"📊 Processing {csv_file}...")
            
            try:
                # Read CSV with proper handling
                df = pd.read_csv(csv_file, dtype=str, keep_default_na=False, encoding='utf-8')
                
                # Clean column names
                df.columns = df.columns.str.strip()
                
                print(f"   📋 Columns: {list(df.columns)}")
                
                # Handle specific tables
                if table_name == 'stops':
                    print("   🔧 Processing stops data...")
                    # Ensure numeric coordinates
                    if 'stop_lat' in df.columns and 'stop_lon' in df.columns:
                        df['stop_lat'] = pd.to_numeric(df['stop_lat'], errors='coerce')
                        df['stop_lon'] = pd.to_numeric(df['stop_lon'], errors='coerce')
                        # Remove invalid coordinates
                        original_count = len(df)
                        df = df.dropna(subset=['stop_lat', 'stop_lon'])
                        if len(df) < original_count:
                            print(f"   ⚠️  Removed {original_count - len(df)} stops with invalid coordinates")
                    
                elif table_name == 'stop_times':
                    print("   🔧 Processing stop_times data...")
                    # Convert stop_sequence to integer
                    if 'stop_sequence' in df.columns:
                        df['stop_sequence'] = pd.to_numeric(df['stop_sequence'], errors='coerce')
                        df = df.dropna(subset=['stop_sequence'])
                        df['stop_sequence'] = df['stop_sequence'].astype(int)
                    
                elif table_name == 'shapes':
                    print("   🔧 Processing shapes data...")
                    # Handle shape coordinates
                    shape_cols = ['shape_pt_lat', 'shape_pt_lon', 'shape_pt_sequence']
                    for col in shape_cols:
                        if col in df.columns:
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                    
                    # Remove rows with invalid shape data
                    valid_shape_cols = [col for col in shape_cols if col in df.columns]
                    if valid_shape_cols:
                        df = df.dropna(subset=valid_shape_cols)
                
                # Write to SQLite
                df.to_sql(table_name, conn, index=False, if_exists='replace')
                
                stats[table_name] = len(df)
                print(f"   ✅ {len(df):,} records imported")
                
            except Exception as e:
                print(f"   ❌ Error processing {csv_file}: {e}")
                stats[table_name] = 0
        else:
            print(f"   ⚠️  {csv_file} not found, skipping...")
            stats[table_name] = 0
    
    # Create basic indexes
    print("\n🔧 Creating indexes...")
    
    basic_indexes = [
        "CREATE INDEX IF NOT EXISTS idx_stops_id ON stops(stop_id);",
        "CREATE INDEX IF NOT EXISTS idx_routes_id ON routes(route_id);",
        "CREATE INDEX IF NOT EXISTS idx_trips_id ON trips(trip_id);",
        "CREATE INDEX IF NOT EXISTS idx_stop_times_stop ON stop_times(stop_id);",
        "CREATE INDEX IF NOT EXISTS idx_stop_times_trip ON stop_times(trip_id);",
    ]
    
    # Only create location index if we have coordinate columns
    try:
        cursor.execute("SELECT stop_lat, stop_lon FROM stops LIMIT 1;")
        basic_indexes.append("CREATE INDEX IF NOT EXISTS idx_stops_location ON stops(stop_lat, stop_lon);")
        print("   ✅ Will create location index")
    except:
        print("   ⚠️  No coordinate columns found, skipping location index")
    
    for idx_sql in basic_indexes:
        try:
            cursor.execute(idx_sql)
            print("   ✅ Index created")
        except Exception as e:
            print(f"   ⚠️  Index warning: {e}")
    
    # Optimize database
    print("\n⚡ Optimizing database...")
    cursor.execute("ANALYZE;")
    cursor.execute("VACUUM;")
    
    # Get final database size
    cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size();")
    db_size = cursor.fetchone()[0]
    
    conn.commit()
    conn.close()
    
    # Print summary
    print("\n" + "="*60)
    print("🎉 BMTC Database Created Successfully!")
    print("="*60)
    print(f"📁 Database: {db_path}")
    print(f"💾 Size: {db_size/1024/1024:.1f} MB")
    print(f"📅 Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n📊 Table Statistics:")
    
    total_records = 0
    for table, count in stats.items():
        if count > 0:
            print(f"   📋 {table:15}: {count:,} records")
            total_records += count
    
    print(f"\n📈 Total Records: {total_records:,}")
    
    # Quick test
    test_database_basic(db_path)
    
    return db_path

def test_database_basic(db_path):
    """Basic database test"""
    print("\n🧪 Quick Database Test...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # List all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"✅ Tables created: {len(tables)}")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]};")
            count = cursor.fetchone()[0]
            print(f"   📋 {table[0]}: {count:,} records")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
    
    conn.close()
    print("\n🎯 Database is ready!")

if __name__ == "__main__":
    print("🚌 BMTC Database Creator - Simple Version")
    print("=" * 50)
    
    # Check if we're in the right directory
    csv_files = [f for f in os.listdir('.') if f.endswith('.csv')]
    
    if len(csv_files) == 0:
        print("❌ No CSV files found in current directory")
        print(f"Current directory: {os.getcwd()}")
        exit(1)
    
    print(f"📁 Found {len(csv_files)} CSV files in current directory")
    
    # Create database
    db_file = create_bmtc_database()
    
    print(f"\n🚀 Next Steps:")
    print(f"1. Database created: {db_file}")
    print(f"2. Copy to your web directory: cp {db_file} /path/to/web/app/")
    print(f"3. Update bmtc_web_api.js to use this database")
    print(f"4. Test your application!")
