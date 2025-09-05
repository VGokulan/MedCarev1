// static/js/dashboard.js

// Global variables to hold chart instances
let riskScoringChart, riskTierChart, roiChart;

document.addEventListener('DOMContentLoaded', function() {
    // Register the datalabels plugin globally
    Chart.register(ChartDataLabels);

    // Initial chart rendering
    updateDashboard();

    // Add event listeners to filters for reactivity
    document.getElementById('riskFilter').addEventListener('change', updateDashboard);
    document.getElementById('ageFilter').addEventListener('change', updateDashboard);
    
    // Add listener for theme changes to redraw charts with new colors
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            // Delay to allow CSS variables to update before redrawing
            setTimeout(updateDashboard, 100);
        });
    }
});

/**
 * Reads CSS variables to make chart colors theme-aware.
 * @returns {object} An object with color values for charts.
 */
function getThemeColors() {
    const styles = getComputedStyle(document.documentElement);
    return {
        primary: styles.getPropertyValue('--text-primary').trim(),
        secondary: styles.getPropertyValue('--text-secondary').trim(),
        border: styles.getPropertyValue('--border-color').trim(),
        accent: styles.getPropertyValue('--accent-color').trim(),
        background: styles.getPropertyValue('--bg-secondary').trim(),
        riskTiers: {
            tier1: '#10b981', tier2: '#22c55e', tier3: '#f59e0b',
            tier4: '#f97316', tier5: '#ef4444'
        },
        roi: { savings: '#10b981', costs: '#ef4444' }
    };
}

/**
 * Creates a baseline configuration for all charts.
 * @param {object} colors - The theme colors object.
 * @returns {object} A Chart.js options object.
 */
function getCommonChartOptions(colors) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'bottom',
                labels: { color: colors.primary, font: { size: 12 } }
            },
            tooltip: {
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                titleFont: { size: 14, weight: 'bold' },
                bodyFont: { size: 12 },
                padding: 10, cornerRadius: 4, displayColors: false
            },
            datalabels: {
                color: '#ffffff',
                font: { weight: 'bold' },
                formatter: (value) => (value !== 0 ? Math.round(value * 100) / 100 : '')
            }
        },
        scales: {
            x: { ticks: { color: colors.secondary }, grid: { color: colors.border } },
            y: { ticks: { color: colors.secondary }, grid: { color: colors.border } }
        },
        animation: { duration: 800, easing: 'easeInOutQuart' }
    };
}

/**
 * Displays a loading spinner inside a chart's container.
 * @param {string} chartId - The ID of the canvas element.
 */
function showLoader(chartId) {
    const chartContent = document.getElementById(chartId).parentElement;
    if (chartContent.querySelector('.loader')) return; // Loader already exists
    const loader = document.createElement('div');
    loader.className = 'loader';
    chartContent.appendChild(loader);
}

/**
 * Removes the loading spinner from a chart's container.
 * @param {string} chartId - The ID of the canvas element.
 */
function hideLoader(chartId) {
    const chartContent = document.getElementById(chartId).parentElement;
    const loader = chartContent.querySelector('.loader');
    if (loader) loader.remove();
}

/**
 * Main function to fetch data and update all charts based on filters.
 */
async function updateDashboard() {
    const riskTier = document.getElementById('riskFilter').value;
    const ageRange = document.getElementById('ageFilter').value;
    const queryParams = new URLSearchParams({ risk_tier: riskTier, age_range: ageRange });

    const chartIds = ['riskScoringChart', 'riskTierChart', 'roiChart'];
    chartIds.forEach(showLoader);

    try {
        const response = await fetch(`/api/dashboard_data?${queryParams.toString()}`);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        const data = await response.json();

        // Destroy existing charts to prevent rendering issues
        if (riskScoringChart) riskScoringChart.destroy();
        if (riskTierChart) riskTierChart.destroy();
        if (roiChart) roiChart.destroy();

        const colors = getThemeColors();
        const commonOptions = getCommonChartOptions(colors);

        createRiskScoringChart(data.risk_scores, commonOptions, colors);
        createRiskTierChart(data.risk_tier_distribution, commonOptions, colors);
        createRoiChart(data.intervention_roi, commonOptions, colors);
        updateRoiSummary(data.intervention_roi);

    } catch (error) {
        console.error("Failed to update dashboard:", error);
    } finally {
        chartIds.forEach(hideLoader);
    }
}

function createRiskScoringChart(data, options, colors) {
    const ctx = document.getElementById('riskScoringChart').getContext('2d');
    riskScoringChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['30-Day Risk', '60-Day Risk', '90-Day Risk'],
            datasets: [{
                label: 'Avg. Hospitalization Risk',
                data: [data.avg_30d, data.avg_60d, data.avg_90d],
                backgroundColor: [colors.accent, colors.riskTiers.tier3, colors.riskTiers.tier5],
                borderColor: colors.background, borderWidth: 2, borderRadius: 5
            }]
        },
        options: {
            ...options,
            plugins: { ...options.plugins,
                datalabels: { ...options.plugins.datalabels,
                     formatter: (value) => value > 0 ? `${(value * 100).toFixed(1)}%` : '',
                     anchor: 'end', align: 'top', color: colors.primary
                },
                tooltip: { ...options.plugins.tooltip, callbacks: {
                        label: (c) => `Avg. Risk: ${(c.raw * 100).toFixed(2)}%`
                    }
                }
            },
            scales: { ...options.scales,
                y: { ...options.scales.y, beginAtZero: true, title: { display: true, text: 'Average Risk Score', color: colors.secondary },
                    ticks: { callback: value => `${(value * 100).toFixed(0)}%` }
                }
            }
        }
    });
}

function createRiskTierChart(data, options, colors) {
    const ctx = document.getElementById('riskTierChart').getContext('2d');
    riskTierChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.map(item => `Tier ${item.risk_tier}`),
            datasets: [{
                label: 'Patients',
                data: data.map(item => item.count),
                backgroundColor: Object.values(colors.riskTiers),
                borderColor: colors.background, borderWidth: 4, hoverOffset: 10
            }]
        },
        options: { ...options, cutout: '60%',
            plugins: { ...options.plugins,
                 datalabels: { ...options.plugins.datalabels,
                     formatter: (value, context) => {
                         const total = context.chart.data.datasets[0].data.reduce((a, b) => a + b, 0);
                         return total > 0 ? `${((value / total) * 100).toFixed(1)}%` : '0%';
                     }
                 },
                 tooltip: { ...options.plugins.tooltip, callbacks: {
                        label: (c) => `${c.label}: ${c.raw.toLocaleString()} patients`
                    }
                }
            }
        }
    });
}

function createRoiChart(data, options, colors) {
    const ctx = document.getElementById('roiChart').getContext('2d');
    roiChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Projected Savings vs. Costs'],
            datasets: [
                { label: 'Projected Savings', data: [data.total_savings], backgroundColor: colors.roi.savings, borderWidth: 0, borderRadius: 5 },
                { label: 'Intervention Costs', data: [data.total_costs], backgroundColor: colors.roi.costs, borderWidth: 0, borderRadius: 5 }
            ]
        },
        options: { ...options, indexAxis: 'y',
             plugins: { ...options.plugins,
                datalabels: { ...options.plugins.datalabels, formatter: (v) => v > 0 ? `$${(v / 1000).toFixed(1)}k` : '' },
                tooltip: { ...options.plugins.tooltip, callbacks: {
                        label: (c) => `${c.dataset.label}: $${Math.round(c.raw).toLocaleString()}`
                    }
                }
            },
            scales: {
                x: { ...options.scales.x, title: { display: true, text: 'Amount (USD)', color: colors.secondary },
                    ticks: { callback: value => `$${value / 1000}k` }
                },
                y: { ...options.scales.y, grid: { display: false } }
            }
        }
    });
}

function updateRoiSummary(data) {
    const formatCurrency = (value) => {
        if (!value) return '$0';
        if (Math.abs(value) >= 1000000) return `$${(value / 1000000).toFixed(2)}M`;
        if (Math.abs(value) >= 1000) return `$${(value / 1000).toFixed(1)}k`;
        return `$${Math.round(value)}`;
    };
    
    document.getElementById('totalSavings').textContent = formatCurrency(data.total_savings);
    document.getElementById('totalCosts').textContent = formatCurrency(data.total_costs);
    document.getElementById('netRoi').textContent = formatCurrency(data.total_savings - data.total_costs);
}
