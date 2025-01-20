// Update teams list
function updateTeamsList() {
    fetch('/api/teams')
        .then(response => response.json())
        .then(teams => {
            const teamsList = document.getElementById('teamsList');
            if (teamsList) {
                teamsList.innerHTML = '';
                teams.forEach(team => {
                    const teamCard = document.createElement('div');
                    teamCard.className = 'card mb-3';
                    teamCard.innerHTML = `
                        <div class="card-body">
                            <h5 class="card-title">${team.name}</h5>
                            <div class="btn-group">
                                <button class="btn btn-primary btn-sm" onclick="editTeam('${team.id}')">Edit</button>
                                <button class="btn btn-danger btn-sm" onclick="deleteTeam('${team.id}')">Delete</button>
                            </div>
                        </div>
                    `;
                    teamsList.appendChild(teamCard);
                });
            }
        })
        .catch(error => showAlert('danger', 'Error updating teams list'));
}

// Update applications list
function updateApplicationsList() {
    fetch('/api/applications')
        .then(response => response.json())
        .then(applications => {
            const notStartedList = document.getElementById('notStartedList');
            const inProgressList = document.getElementById('inProgressList');
            const completedList = document.getElementById('completedList');
            
            if (notStartedList) notStartedList.innerHTML = '';
            if (inProgressList) inProgressList.innerHTML = '';
            if (completedList) completedList.innerHTML = '';

            applications.forEach(app => {
                const appCard = createApplicationCard(app);
                if (app.state === 'notStarted' && notStartedList) {
                    notStartedList.appendChild(appCard);
                } else if (app.state === 'inProgress' && inProgressList) {
                    inProgressList.appendChild(appCard);
                } else if (app.state === 'completed' && completedList) {
                    completedList.appendChild(appCard);
                }
            });
        })
        .catch(error => showAlert('danger', 'Error updating applications list'));
}

// Create application card
function createApplicationCard(app) {
    const card = document.createElement('div');
    card.className = 'card mb-2 application-card';
    card.id = `app-${app.id}`;
    card.draggable = true;
    card.ondragstart = (e) => drag(e);

    let systemsHtml = '';
    if (app.systems && app.systems.length > 0) {
        systemsHtml = `
            <div class="mt-2">
                <small class="text-muted">Systems:</small>
                ${app.systems.map(system => `
                    <div class="d-flex justify-content-between align-items-center mt-1">
                        <span class="small">${system.name}</span>
                        ${system.webui_url ? `<a href="${system.webui_url}" target="_blank" class="system-url">🔗</a>` : ''}
                        ${system.port ? `<span class="port-badge">:${system.port}</span>` : ''}
                        <span class="badge bg-${system.status === 'running' ? 'success' : 'secondary'}">${system.status}</span>
                        <button class="btn btn-danger btn-sm" onclick="deleteSystem('${system.id}')">Delete</button>
                    </div>
                `).join('')}
            </div>
        `;
    }

    card.innerHTML = `
        <div class="card-body">
            <div class="d-flex justify-content-between align-items-center">
                <div>
                    <h6 class="mb-1">${app.name}</h6>
                    <small>Team: ${app.team.name}</small>
                </div>
                <div>
                    <button class="btn btn-primary btn-sm" onclick="runTest('${app.id}')">Run Test</button>
                    <button class="btn btn-danger btn-sm" onclick="deleteApplication('${app.id}')">Delete</button>
                </div>
            </div>
            ${systemsHtml}
            <div class="mt-2">
                <small class="text-muted">Test Status:</small>
                <span class="test-status" id="test-status-${app.id}"></span>
            </div>
        </div>
    `;
    return card;
}

// Run test for application
function runTest(appId) {
    fetch(`/api/applications/${appId}/test`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        showAlert('success', 'Test started');
        pollTestStatus(appId);
    })
    .catch(error => showAlert('danger', 'Error starting test'));
}

// Poll test status
function pollTestStatus(appId, interval = 2000) {
    const statusElement = document.getElementById(`test-status-${appId}`);
    if (!statusElement) return;

    const checkStatus = () => {
        fetch(`/api/applications/${appId}/systems`)
            .then(response => response.json())
            .then(systems => {
                const allRunning = systems.every(system => system.status === 'running');
                statusElement.innerHTML = `
                    <span class="badge bg-${allRunning ? 'success' : 'warning'}">
                        ${allRunning ? 'All Systems Running' : 'Systems Starting'}
                    </span>
                `;
                if (!allRunning) {
                    setTimeout(checkStatus, interval);
                }
            })
            .catch(error => {
                statusElement.innerHTML = `
                    <span class="badge bg-danger">Error checking status</span>
                `;
            });
    };

    checkStatus();
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    updateTeamsList();
    updateApplicationsList();
    
    // Set up auto-refresh
    setInterval(updateTeamsList, 10000);
    setInterval(updateApplicationsList, 10000);
});

// Drag and drop functions
function allowDrop(ev) {
    ev.preventDefault();
}

function drag(ev) {
    ev.dataTransfer.setData("text", ev.target.id);
}

function drop(ev) {
    ev.preventDefault();
    const data = ev.dataTransfer.getData("text");
    const draggedElement = document.getElementById(data);
    const dropzone = ev.target.closest('[ondrop]');
    
    if (dropzone && draggedElement) {
        const appId = draggedElement.id.replace('app-', '');
        const newState = dropzone.id.replace('List', '');
        
        updateApplicationState(appId, newState)
            .then(() => {
                dropzone.appendChild(draggedElement);
            })
            .catch(error => {
                showAlert('danger', 'Error updating application state');
            });
    }
}

// Update application state
function updateApplicationState(appId, state) {
    return fetch(`/api/applications/${appId}/state`, {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ state: state })
    })
    .then(response => {
        if (!response.ok) throw new Error('Failed to update state');
        return response.json();
    });
}

function handleImport(event) {
    event.preventDefault();
    const fileInput = document.getElementById('importFile');
    const file = fileInput.files[0];
    
    if (!file) {
        alert('Please select a file');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    fetch('/api/import', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert(data.error);
        } else {
            alert('Import successful');
            location.reload();
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Import failed');
    });
}
