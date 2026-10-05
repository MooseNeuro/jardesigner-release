import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import {
    Box, Button, Autocomplete, TextField,
    CircularProgress, TablePagination, Typography,
} from '@mui/material';
import { API_BASE_URL } from '../../config.js';

function layerSortKey(l) {
    if (l.includes('/')) {
        const [a, b] = l.split('/').map(Number);
        return a + 1 / (b + 1);
    }
    const m = l.match(/^(\d+)([a-z]?)$/);
    if (m) return Number(m[1]) + ({ a: 0.1, b: 0.2, c: 0.3 }[m[2]] || 0);
    return 99;
}

const SPECIES_OPTIONS = ['Homo Sapiens', 'Mus musculus'];
const DEFAULT_PAGE_SIZE = 20;
const PAGE_SIZE_OPTIONS = [20, 50, 100];

const toItem = (s) => ({
    id:              `ab_${s.specimen__id}`,
    name:            s.specimen__name || `Specimen ${s.specimen__id}`,
    source:          `AllenBrain/${s.donor__species || ''}`,
    description:     [s.structure__acronym, s.structure__layer, s.tag__dendrite_type].filter(Boolean).join(' · '),
    source_type:     'swc',
    topTen:          false,
    server_file:     `ab_${s.specimen__id}`,
    staged_filename: `ab_${s.specimen__id}`,
});

export default function AllenBrainSearchForm({ onResults, footerEl, baseUrl = API_BASE_URL }) {
    // Search bar state
    const [species, setSpecies]     = useState(null);
    const [area, setArea]           = useState(null);
    const [layer, setLayer]         = useState(null);
    const [lineName, setLineName]   = useState(null);
    const [meta, setMeta]           = useState(null);
    const [metaLoading, setMetaLoading] = useState(false);

    // Results state
    const [loading, setLoading]     = useState(false);
    const [error, setError]         = useState(null);
    const [page, setPage]           = useState(0);
    const [pageSize, setPageSize]   = useState(DEFAULT_PAGE_SIZE);
    const [rowCount, setRowCount]   = useState(0);
    const lastQuery = useRef(null);

    useEffect(() => {
        setArea(null); setLayer(null); setLineName(null);
        if (!species) { setMeta(null); return; }
        const controller = new AbortController();
        setMetaLoading(true);
        fetch(`${baseUrl}/allenbrain/metadata?species=${encodeURIComponent(species)}`, { signal: controller.signal })
            .then(r => r.json())
            .then(d => setMeta(d))
            .catch(e => { if (e.name !== 'AbortError') console.error(e); })
            .finally(() => setMetaLoading(false));
        return () => controller.abort();
    }, [species, baseUrl]);

    const areaMap = {};
    (meta?.brain_areas || []).forEach(a => { areaMap[a.acronym] = a; });
    const areaOpts  = Object.keys(areaMap).sort((a, b) => a.localeCompare(b));
    const layerOpts = (meta?.layers || []).slice().sort((a, b) => layerSortKey(a) - layerSortKey(b));
    const lineOpts  = species === 'Mus musculus' ? (meta?.line_names || []) : [];

    const _fetchPage = async (query, pg, pgSize, { showSpinner = false } = {}) => {
        if (showSpinner) setLoading(true);
        setError(null);
        try {
            const resp = await fetch(`${baseUrl}/allenbrain/search`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...query, page: pg, size: pgSize }),
            });
            if (!resp.ok) throw new Error('Search failed');
            const data = await resp.json();
            setRowCount(data.total || 0);
            setPage(pg);
            onResults((data.neurons || []).map(toItem));
        } catch (e) {
            setError(e.message);
            setRowCount(0);
            onResults([]);
        } finally {
            if (showSpinner) setLoading(false);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!species) return;
        const entry    = area ? areaMap[area] : null;
        const isParent = entry?.is_parent ?? false;
        const query = {
            species,
            brain_area_acronym:        isParent ? '' : (area || ''),
            brain_area_parent_acronym: isParent ? area : '',
            layer:     layer    || '',
            line_name: lineName || '',
        };
        lastQuery.current = query;
        await _fetchPage(query, 0, pageSize, { showSpinner: true });
    };

    const handlePageChange = async (_, newPage) => {
        if (lastQuery.current) await _fetchPage(lastQuery.current, newPage, pageSize);
    };

    const handleRowsPerPageChange = async (e) => {
        const newSize = parseInt(e.target.value, 10);
        setPageSize(newSize);
        if (lastQuery.current) await _fetchPage(lastQuery.current, 0, newSize);
    };

    const pagination = rowCount > 0 && (
        <TablePagination
            component="div"
            count={rowCount}
            page={page}
            rowsPerPage={pageSize}
            rowsPerPageOptions={PAGE_SIZE_OPTIONS}
            onPageChange={handlePageChange}
            onRowsPerPageChange={handleRowsPerPageChange}
            sx={{ borderTop: '1px solid #e0e0e0' }}
        />
    );

    return (
        <>
            <Box>
                <form onSubmit={handleSubmit}>
                    <Box sx={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
                        <Autocomplete
                            size="small" sx={{ width: 200 }}
                            options={SPECIES_OPTIONS}
                            value={species}
                            onChange={(_, val) => setSpecies(val)}
                            disabled={loading}
                            renderInput={(params) => <TextField {...params} label="Species" size="small" variant="outlined" />}
                        />
                        <Autocomplete
                            size="small" sx={{ width: 220, display: species ? 'inline-flex' : 'none' }}
                            options={areaOpts}
                            value={area}
                            onChange={(_, val) => setArea(val)}
                            disabled={!species || loading || metaLoading}
                            loading={metaLoading}
                            getOptionLabel={opt => `${opt} — ${areaMap[opt]?.name || ''}`}
                            renderInput={(params) => (
                                <TextField {...params} label="Brain Area" size="small" variant="outlined"
                                    InputProps={{ ...params.InputProps, endAdornment: (<>{metaLoading ? <CircularProgress size={14} sx={{ mr: 1 }} /> : null}{params.InputProps.endAdornment}</>) }}
                                />
                            )}
                        />
                        <Autocomplete
                            size="small" sx={{ width: 140, display: species ? 'inline-flex' : 'none' }}
                            options={layerOpts}
                            value={layer}
                            onChange={(_, val) => setLayer(val)}
                            disabled={!species || loading || metaLoading}
                            loading={metaLoading}
                            getOptionLabel={opt => `Layer ${opt}`}
                            renderInput={(params) => <TextField {...params} label="Layer" size="small" variant="outlined" />}
                        />
                        <Autocomplete
                            size="small" sx={{ width: 200, display: species === 'Mus musculus' ? 'inline-flex' : 'none' }}
                            options={lineOpts}
                            value={lineName}
                            onChange={(_, val) => setLineName(val)}
                            disabled={!species || loading || metaLoading}
                            loading={metaLoading}
                            renderInput={(params) => <TextField {...params} label="Transgenic Line" size="small" variant="outlined" />}
                        />
                        <Button size="small" type="submit" variant="contained" disabled={loading || !species}>
                            Search
                        </Button>
                    </Box>
                </form>
                {error && <Typography color="error" variant="body2" sx={{ mt: 0.5 }}>{error}</Typography>}
            </Box>
            {footerEl && pagination && createPortal(pagination, footerEl)}
        </>
    );
}
