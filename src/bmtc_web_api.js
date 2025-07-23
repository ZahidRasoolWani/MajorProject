// --- FIXED BMTC WEB API ---
class BMTCRouteAPI {
    constructor(dbPath = './bmtc_routes.db') {
        this.dbPath = dbPath;
        this.db = null;
        this.ready = false;
        
        this.cache = {
            nearbyStops: new Map(),
            routeConnections: new Map(),
            stopDetails: new Map(),
            allStops: null
        };
        
        this.maxTransfers = 3;
        this.maxSearchDepth = 100;
        this.queryTimeout = 15000;
    }
    
    async initSQL() {
        try {
            console.log(' Loading BMTC Database (274MB)...');
            
            if (typeof window.SQL === 'undefined') {
                await this.loadSQLJS();
            }
            
            const SQL = await initSqlJs({
                locateFile: file => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.8.0/${file}`
            });
            
            console.log(' Loading database file...');
            const response = await fetch(this.dbPath);
            if (!response.ok) {
                throw new Error(`Database not found: ${response.status}`);
            }
            
            const data = await response.arrayBuffer();
            this.db = new SQL.Database(new Uint8Array(data));
            
            this.ready = true;
            console.log(' BMTC Database loaded successfully!');
            this.showDatabaseStats();
            
        } catch (error) {
            console.error(' Database loading failed:', error);
            this.ready = false;
            throw error;
        }
    }
    
    async loadSQLJS() {
        const cdnUrls = [
            'https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.8.0/sql-wasm.js',
            'https://unpkg.com/sql.js@1.8.0/dist/sql-wasm.js'
        ];
        
        for (const url of cdnUrls) {
            try {
                await this.loadScriptFromUrl(url);
                console.log(' SQL.js loaded');
                return;
            } catch (error) {
                console.warn(`Failed to load from ${url}`);
            }
        }
        throw new Error('Could not load SQL.js from any CDN');
    }
    
    loadScriptFromUrl(url) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = url;
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
            setTimeout(() => reject(new Error('Timeout')), 10000);
        });
    }
    
    showDatabaseStats() {
        try {
            const stops = this.db.exec("SELECT COUNT(*) FROM stops")[0].values[0][0];
            const routes = this.db.exec("SELECT COUNT(*) FROM routes")[0].values[0][0];
            const trips = this.db.exec("SELECT COUNT(*) FROM trips")[0].values[0][0];
            
            console.log(` BMTC Database Stats:`);
            console.log(`    Stops: ${stops.toLocaleString()}`);
            console.log(`    Routes: ${routes.toLocaleString()}`);
            console.log(`    Trips: ${trips.toLocaleString()}`);
        } catch (error) {
            console.warn('Stats unavailable:', error);
        }
    }
    
    findNearbyStops(lat, lon, radiusKm = 1.5) {
        if (!this.ready) return [];
        
        const cacheKey = `${lat.toFixed(4)}_${lon.toFixed(4)}_${radiusKm}`;
        if (this.cache.nearbyStops.has(cacheKey)) {
            return this.cache.nearbyStops.get(cacheKey);
        }
        
        const latRange = radiusKm / 111;
        const lonRange = radiusKm / (111 * Math.cos(lat * Math.PI / 180));
        
        const query = `
            SELECT stop_id, stop_name, stop_lat, stop_lon
            FROM stops 
            WHERE stop_lat BETWEEN ? AND ? 
              AND stop_lon BETWEEN ? AND ?
              AND stop_name IS NOT NULL
            ORDER BY 
                ((stop_lat - ?) * (stop_lat - ?) + (stop_lon - ?) * (stop_lon - ?))
            LIMIT 20
        `;
        
        try {
            const result = this.db.exec(query, [
                lat - latRange, lat + latRange,
                lon - lonRange, lon + lonRange,
                lat, lat, lon, lon
            ]);
            
            if (!result || result.length === 0) return [];
            
            const stops = result[0].values.map(row => {
                const distance = this.calculateDistance(lat, lon, row[2], row[3]);
                return {
                    stop_id: row[0],
                    stop_name: row[1],
                    stop_lat: row[2],
                    stop_lon: row[3],
                    distance: Math.round(distance)
                };
            }).filter(stop => stop.distance <= radiusKm * 1000)
              .sort((a, b) => a.distance - b.distance);
            
            this.cache.nearbyStops.set(cacheKey, stops);
            return stops;
            
        } catch (error) {
            console.error('Nearby stops query failed:', error);
            return [];
        }
    }
    
    getAllStops() {
        if (!this.ready) return [];
        
        if (this.cache.allStops) {
            return this.cache.allStops;
        }
        
        const query = `
            SELECT DISTINCT stop_id, stop_name, stop_lat, stop_lon
            FROM stops 
            WHERE stop_name IS NOT NULL 
              AND stop_name != ''
              AND LENGTH(TRIM(stop_name)) > 2
            ORDER BY stop_name
            LIMIT 2000
        `;
        
        try {
            const result = this.db.exec(query);
            if (!result || result.length === 0) return [];
            
            const stops = result[0].values.map(row => ({
                stop_id: row[0],
                stop_name: row[1],
                stop_lat: row[2],
                stop_lon: row[3]
            }));
            
            this.cache.allStops = stops;
            return stops;
            
        } catch (error) {
            console.error('Get all stops failed:', error);
            return [];
        }
    }
    
    // FIXED: Main route finding function
    async findOptimalRoutes(fromStopId, toStopId, maxTransfers = 2) {
        if (!this.ready) {
            console.log(' Database not ready');
            return [];
        }
        
        console.log(`🔍 Searching routes: ${fromStopId} → ${toStopId} (max ${maxTransfers} transfers)`);
        
        try {
            // Step 1: Try direct routes first
            const directRoutes = this.findDirectRoutes(fromStopId, toStopId);
            console.log(` Direct routes found: ${directRoutes.length}`);
            
            if (directRoutes.length > 0) {
                console.log(` Returning ${directRoutes.length} direct routes`);
                return directRoutes;
            }
            
            // Step 2: Try transfer routes if no direct routes and maxTransfers > 0
            if (maxTransfers > 0) {
                const transferRoutes = await this.findTransferRoutes(fromStopId, toStopId, maxTransfers);
                console.log(` Transfer routes found: ${transferRoutes.length}`);
                
                if (transferRoutes.length > 0) {
                    console.log(` Returning ${transferRoutes.length} transfer routes`);
                    return transferRoutes;
                }
            }
            
            console.log(' No routes found at all');
            return [];
            
        } catch (error) {
            console.error(' Route search failed:', error);
            return [];
        }
    }
    
    // FIXED: Direct routes function
    findDirectRoutes(fromStopId, toStopId) {
    console.log(`🔍 Searching direct routes: ${fromStopId} → ${toStopId}`);
    
    const query = `
        SELECT DISTINCT 
            r.route_short_name,
            r.route_long_name,
            st1.departure_time,
            st2.arrival_time,
            (st2.stop_sequence - st1.stop_sequence) as stop_count,
            s1.stop_name as from_stop_name,
            s2.stop_name as to_stop_name
        FROM stop_times st1
        JOIN stop_times st2 ON st1.trip_id = st2.trip_id
        JOIN trips t ON st1.trip_id = t.trip_id
        JOIN routes r ON t.route_id = r.route_id
        JOIN stops s1 ON st1.stop_id = s1.stop_id
        JOIN stops s2 ON st2.stop_id = s2.stop_id
        WHERE st1.stop_id = ? 
          AND st2.stop_id = ?
          AND st1.stop_sequence < st2.stop_sequence
        ORDER BY stop_count ASC
        LIMIT 5
    `;
    
    try {
        const result = this.db.exec(query, [fromStopId, toStopId]);
        
        if (!result || result.length === 0 || !result[0].values || result[0].values.length === 0) {
            console.log(' No direct routes found in database');
            return [];
        }
        
        const routes = result[0].values.map((row, index) => {
            return {
                type: 'direct',
                transfers: 0,
                totalTime: 45,
                legs: [{
                    routeNumber: row[0],
                    routeName: `${row[5]} → ${row[6]}`, // User's actual journey
                    routeDescription: row[1], // Original route description
                    fromStopId,
                    toStopId,
                    fromStopName: row[5],
                    toStopName: row[6],
                    departureTime: row[2] || 'N/A',
                    arrivalTime: row[3] || 'N/A'
                }]
            };
        });
        
        return routes;
        
    } catch (error) {
        console.error(' Direct route SQL query failed:', error);
        return [];
    }
}

    
    // IMPROVED: Transfer routes function
    async findTransferRoutes(fromStopId, toStopId, maxTransfers) {
    console.log(` Searching transfer routes: ${fromStopId} → ${toStopId} (max ${maxTransfers})`);
    
    // Enhanced one-transfer search with stop names
    const oneTransferQuery = `
        SELECT DISTINCT 
            r1.route_short_name as route1,
            r1.route_long_name as route1_name,
            st_transfer.stop_id as transfer_stop_id,
            s_transfer.stop_name as transfer_stop_name,
            r2.route_short_name as route2,
            r2.route_long_name as route2_name,
            s_from.stop_name as from_stop_name,
            s_to.stop_name as to_stop_name
        FROM stop_times st1
        JOIN stop_times st_transfer ON st1.trip_id = st_transfer.trip_id
        JOIN trips t1 ON st1.trip_id = t1.trip_id
        JOIN routes r1 ON t1.route_id = r1.route_id
        JOIN stops s_transfer ON st_transfer.stop_id = s_transfer.stop_id
        JOIN stops s_from ON st1.stop_id = s_from.stop_id
        JOIN stop_times st2 ON st_transfer.stop_id = st2.stop_id
        JOIN stop_times st3 ON st2.trip_id = st3.trip_id
        JOIN trips t2 ON st2.trip_id = t2.trip_id
        JOIN routes r2 ON t2.route_id = r2.route_id
        JOIN stops s_to ON st3.stop_id = s_to.stop_id
        WHERE st1.stop_id = ?
          AND st3.stop_id = ?
          AND st1.stop_sequence < st_transfer.stop_sequence
          AND st2.stop_sequence < st3.stop_sequence
          AND t1.trip_id != t2.trip_id
        LIMIT 3
    `;
    
    try {
        const result = this.db.exec(oneTransferQuery, [fromStopId, toStopId]);
        
        if (!result || result.length === 0 || !result[0].values || result[0].values.length === 0) {
            console.log(' No one-transfer routes found');
            return [];
        }
        
        const routes = result[0].values.map((row, index) => {
            console.log(` Found transfer route ${index + 1}: ${row[0]} → ${row[4]} (via ${row[3]})`);
            return {
                type: 'transfer',
                transfers: 1,
                totalTime: 65, // Estimated time with transfer
                legs: [
                    {
                        routeNumber: row[0],
                        routeName: `${row[6]} → ${row[3]}`, // User's journey: From Stop → Transfer Stop
                        routeDescription: row[1] || 'BMTC Route', // Original route info
                        fromStopId: fromStopId,
                        toStopId: row[2],
                        fromStopName: row[6], // From stop name
                        toStopName: row[3]    // Transfer stop name
                    },
                    {
                        routeNumber: row[4],
                        routeName: `${row[3]} → ${row[7]}`, // User's journey: Transfer Stop → Destination
                        routeDescription: row[5] || 'BMTC Route', // Original route info
                        fromStopId: row[2],
                        toStopId: toStopId,
                        fromStopName: row[3], // Transfer stop name
                        toStopName: row[7]    // Destination stop name
                    }
                ]
            };
        });
        
        console.log(` Processed ${routes.length} transfer routes successfully`);
        return routes;
        
    } catch (error) {
        console.error(' Transfer route query failed:', error);
        return [];
    }
}

    
    calculateDistance(lat1, lon1, lat2, lon2) {
        const R = 6371000;
        const dLat = (lat2 - lat1) * Math.PI / 180;
        const dLon = (lon2 - lon1) * Math.PI / 180;
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
                Math.sin(dLon/2) * Math.sin(dLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        return R * c;
    }
}

window.BMTCRouteAPI = BMTCRouteAPI;

