document.addEventListener('DOMContentLoaded', () => {
    const socket = io();
    const statusDiv = document.getElementById('connection-status');
    const clockDiv = document.getElementById('clock');

    // Clock
    setInterval(() => {
        const now = new Date();
        clockDiv.textContent = now.toLocaleTimeString();
    }, 1000);

    // Socket Connection Logic
    socket.on('connect', () => {
        statusDiv.textContent = 'Connected';
        statusDiv.classList.remove('offline');
        statusDiv.classList.add('online');
        document.getElementById('disconnect-overlay').classList.remove('visible');

        // Request initial system statuses
        socket.emit('request_status');
    });

    socket.on('disconnect', () => {
        statusDiv.textContent = 'Disconnected';
        statusDiv.classList.remove('online');
        statusDiv.classList.add('offline');
        document.getElementById('disconnect-overlay').classList.add('visible');
    });

    // System Status Updates
    function updateSystemStatus(sysId, status) {
        const el = document.getElementById(`status-${sysId}`);
        if (!el) return;

        el.textContent = status;
        el.className = 'grid-cell system-status'; // reset

        if (status === 'ONLINE' || status === 'RUNNING') el.classList.add('status-online');
        else if (status === 'OFFLINE' || status === 'CLOSED') el.classList.add('status-offline');
        else if (status === 'ERROR') el.classList.add('status-error');
        else if (status === 'CONNECTING') el.classList.add('status-connecting');
    }

    socket.on('status_update', (data) => {
        updateSystemStatus(data.system_id, data.status);
    });

    socket.on('full_status_update', (statuses) => {
        for (const [sysId, status] of Object.entries(statuses)) {
            updateSystemStatus(sysId, status);
        }
    });

    // Command Execution
    document.body.addEventListener('click', (e) => {
        // Use event delegation
        if (!e.target.matches('button')) return;

        const btn = e.target;

        // 1. Global Buttons
        if (btn.classList.contains('global-btn')) {
            const cell = btn.closest('.global-action');
            const actionId = cell.dataset.action;

            // Find all action cells for this action
            const targets = document.querySelectorAll(`.action-cell[data-action="${actionId}"] button`);
            targets.forEach(t => t.click());
            return;
        }

        // 2. Group Buttons
        if (btn.classList.contains('group-btn')) {
            const group = btn.dataset.group;
            const actionId = btn.dataset.action;

            // Find all action cells for this group AND action
            const targets = document.querySelectorAll(`.action-cell[data-group="${group}"][data-action="${actionId}"] button`);
            targets.forEach(t => t.click());
            return;
        }

        // 3. System Buttons
        if (btn.closest('.action-cell')) {
            const cell = btn.closest('.action-cell');
            const systemId = cell.dataset.system;
            const actionId = cell.dataset.action;

            // Optimistic UI update or loading state
            cell.classList.add('loading');
            cell.classList.remove('success', 'error');

            socket.emit('execute_command', {
                system_id: systemId,
                action_id: actionId
            });
        }
    });

    // Handle Results
    socket.on('command_result', (data) => {
        /*
        data = {
            system_id: 'camera1',
            action_id: 'record_toggle',
            status: 'success' | 'error',
            message: '...'
        }
        */
        const selector = `.action-cell[data-system="${data.system_id}"][data-action="${data.action_id}"]`;
        const cell = document.querySelector(selector);

        if (cell) {
            cell.classList.remove('loading');
            if (data.status === 'success') {
                cell.classList.add('success');
                // Optional: remove success class after a few seconds
                setTimeout(() => cell.classList.remove('success'), 2000);
            } else {
                cell.classList.add('error');
                console.error(data.message);
                // Maybe show a toast or tooltip with the error message
            }
        }
    });
});
