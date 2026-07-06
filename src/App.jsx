/* eslint-disable no-unused-vars */
/* eslint-disable react-hooks/exhaustive-deps */
/* eslint-disable react-hooks/set-state-in-effect */
import React, { useState, useEffect } from 'react'
import { Routes, Route, useNavigate, useLocation, Navigate, useParams } from 'react-router-dom'
import HomePage from './gui/components/Homepage'
import Loginpage from './gui/Login/Loginpage'
import ProjectLayout from './gui/components/ProjectLayout'
import ProjectInformationPlaceholder from './gui/components/global_info/ProjectInformationPlaceholder'
import BridgeData from './gui/components/bridgedata/BridgeData'
import FinancialData from './gui/components/financialdata/FinancialData'
import TrafficData from './gui/components/trafficdata/TrafficData'
import ConstructionWorkData from './gui/components/constructionworkdata/ConstructionWorkData'
import CarbonEmissionContainer from './gui/components/carbon_emission/CarbonEmissionContainer'
import Logs from './gui/components/Logs'
import MaintenanceAndRepair from './gui/components/maintenance_and_repair/MaintenanceAndRepair'
import Recycling from './gui/components/recycling/Recycling'
import Demolition from './gui/components/demolition/Demolition'
import Outputs from './gui/components/outputs/Outputs'
import { ProjectDataProvider } from './contexts/ProjectDataContext'
import { buildProjectFromCreation } from './utils/projectCreation'
import { createDefaultProject, normalizeProjectData } from './utils/projectSchema'
import { account, ID } from './lib/appwrite'
import { projectStorageService } from './lib/projectStorageService'
import './App.css'

function ProtectedRoute({ isLoggedIn, children }) {
  if (!isLoggedIn) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

function ProjectViewWrapper({ projectData, setProjectData, logs, setLogs, isLocked, setIsLocked, addLog }) {
  const { projectId, nodeId } = useParams();
  const navigate = useNavigate();
  const activeNode = nodeId ? decodeURIComponent(nodeId) : 'General Information';

  const [dataLoaded, setDataLoaded] = useState(false);
  const [saveState, setSaveState] = useState('saved');

  useEffect(() => {
    if (projectId) {
      setDataLoaded(false);
      const loadData = async () => {
        const saved = await projectStorageService.loadProject(projectId);
        if (saved) {
          try {
            const normalizedSaved = normalizeProjectData(saved);
            // Only update if it's different to avoid loops if navigate is used
            if (JSON.stringify(normalizedSaved) !== JSON.stringify(projectData)) {
              setProjectData(normalizedSaved);
            }
          } catch (e) {
            console.error("Error parsing saved project data", e);
          }
        }
        setDataLoaded(true);
      };
      loadData();
    }
  }, [projectId]);

  useEffect(() => {
    if (projectId && projectData && dataLoaded) {
      setSaveState('saving');
      const timeoutId = setTimeout(async () => {
        try {
          await projectStorageService.saveProject(projectId, projectData);
          setSaveState('saved');
        } catch (error) {
          if (error.message === 'offline') {
            setSaveState('offline');
          } else {
            setSaveState('error');
          }
        }
      }, 500);
      return () => clearTimeout(timeoutId);
    }
  }, [projectData, projectId, dataLoaded]);

  // Handle abrupt closure to ensure debounced data is saved locally
  useEffect(() => {
    const handleBeforeUnload = () => {
      if (projectId && projectData) {
        const storageKey = `project_data_${projectId}`;
        const localWrapper = {
            data: normalizeProjectData({ ...projectData, _lastModified: Date.now() }),
            sync_status: sessionStorage.getItem('isGuest') === 'true' ? 'synced' : 'pending'
        };
        localStorage.setItem(storageKey, JSON.stringify(localWrapper));
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [projectId, projectData]);

  const updateProjectData = (section, data) => {
    setProjectData(prev => ({
      ...prev,
      [section]: data,
      ...(section === 'maintenance_repair_data' ? { maintenance_data: data } : {})
    }))
  }

  const handleSetActiveNode = (node) => {
    if (node !== activeNode) {
      navigate(`/project/${projectId}/${encodeURIComponent(node)}`);
      addLog(`Switched to ${node} view.`);
    }
  }

  const handleNewProject = (data) => {
    const newProjectId = 'new_project_' + Date.now();
    setProjectData(buildProjectFromCreation(data))

    setLogs([])
    setIsLocked(false)
    addLog(`New project '${data?.name || 'New Project'}' created.`)
    navigate(`/project/${newProjectId}/General Information`);
  }

  const handleOpenProject = (data) => {
    const openProjectId = data?.id || 'opened_project';
    const raw = data.project || data;
    setProjectData(normalizeProjectData(raw))

    if (data.logs) {
      setLogs(data.logs)
    } else {
      setLogs([])
    }
    setIsLocked(false)
    addLog(`Project '${data?.name || 'Opened Project'}' opened successfully.`)
    navigate(`/project/${openProjectId}/General Information`);
  }

  const handleClearLogs = () => {
    setLogs([])
  }

  const handleRenameProject = (newName) => {
    if (projectData) {
      setProjectData(prev => ({
        ...prev,
        name: newName,
        general_info: {
          ...(prev.general_info || {}),
          project_name: newName,
        },
      }))
      addLog(`Project renamed to '${newName}'.`)
    }
  }

  const handleExportProject = () => {
    if (!projectData) return;

    const exportData = {
      project: normalizeProjectData(projectData),

      logs: logs,
      exportedAt: new Date().toISOString()
    };

    const storageKey = `lcca_export_${projectData.name || 'unnamed'}`;
    localStorage.setItem(storageKey, JSON.stringify(exportData));

    const dataStr = JSON.stringify(exportData, null, 2);
    const blob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = `${projectData.name || 'project'}_export.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    addLog(`Project exported and saved to local storage as '${storageKey}'.`);
  };

  const CONTENT_MAP = {
    'General Information': <ProjectInformationPlaceholder key="general" />,
    'Bridge Data': <BridgeData key="bridge" data={projectData.bridge_data} onUpdate={(d) => updateProjectData('bridge_data', d)} />,
    'Financial Data': <FinancialData key="financial" data={projectData.financial_data} onUpdate={(d) => updateProjectData('financial_data', d)} />,
    'Traffic Data': <TrafficData key="traffic" data={projectData.traffic_data} onUpdate={(d) => updateProjectData('traffic_data', d)} />,
    'Construction Work Data': <ConstructionWorkData key="cw_main" data={projectData.construction_work_data} onUpdate={(d) => updateProjectData('construction_work_data', d)} setActiveNode={handleSetActiveNode} />,
    'Foundation': <ConstructionWorkData key="cw_foundation" data={projectData.construction_work_data} onUpdate={(d) => updateProjectData('construction_work_data', d)} setActiveNode={handleSetActiveNode} />,
    'Sub Structure': <ConstructionWorkData key="cw_sub" data={projectData.construction_work_data} onUpdate={(d) => updateProjectData('construction_work_data', d)} initialTab="SubStructure" setActiveNode={handleSetActiveNode} />,
    'Super Structure': <ConstructionWorkData key="cw_super" data={projectData.construction_work_data} onUpdate={(d) => updateProjectData('construction_work_data', d)} initialTab="SuperStructure" setActiveNode={handleSetActiveNode} />,
    'Miscellaneous': <ConstructionWorkData key="cw_misc" data={projectData.construction_work_data} onUpdate={(d) => updateProjectData('construction_work_data', d)} initialTab="Miscellaneous" setActiveNode={handleSetActiveNode} />,
    'Carbon Emissions Data': <CarbonEmissionContainer key="ce_main" data={projectData.carbon_emission_data} onUpdate={(d) => updateProjectData('carbon_emission_data', d)} setActiveNode={handleSetActiveNode} />,
    'Carbon Emission Data': <CarbonEmissionContainer key="ce_main_legacy" data={projectData.carbon_emission_data} onUpdate={(d) => updateProjectData('carbon_emission_data', d)} setActiveNode={handleSetActiveNode} />,
    'Social Cost of Carbon': <CarbonEmissionContainer key="ce_social" data={projectData.carbon_emission_data} onUpdate={(d) => updateProjectData('carbon_emission_data', d)} initialTab="SocialCost" setActiveNode={handleSetActiveNode} />,
    'Material Emissions': <CarbonEmissionContainer key="ce_material" data={projectData.carbon_emission_data} onUpdate={(d) => updateProjectData('carbon_emission_data', d)} initialTab="Material" setActiveNode={handleSetActiveNode} />,
    'Transportation Emissions': <CarbonEmissionContainer key="ce_transport" data={projectData.carbon_emission_data} onUpdate={(d) => updateProjectData('carbon_emission_data', d)} initialTab="Transportation" setActiveNode={handleSetActiveNode} />,
    'Machinery/Equipment Emissions': <CarbonEmissionContainer key="ce_machinery" data={projectData.carbon_emission_data} onUpdate={(d) => updateProjectData('carbon_emission_data', d)} initialTab="Machinery" setActiveNode={handleSetActiveNode} />,
    'Machinery Emissions': <CarbonEmissionContainer key="ce_machinery_legacy" data={projectData.carbon_emission_data} onUpdate={(d) => updateProjectData('carbon_emission_data', d)} initialTab="Machinery" setActiveNode={handleSetActiveNode} />,
    'Traffic Rerouting Emissions': <CarbonEmissionContainer key="ce_traffic" data={projectData.carbon_emission_data} onUpdate={(d) => updateProjectData('carbon_emission_data', d)} initialTab="Traffic" setActiveNode={handleSetActiveNode} />,
    'Traffic Diversion Emissions': <CarbonEmissionContainer key="ce_traffic_legacy" data={projectData.carbon_emission_data} onUpdate={(d) => updateProjectData('carbon_emission_data', d)} initialTab="Traffic" setActiveNode={handleSetActiveNode} />,
    'Maintenance and Repair': <MaintenanceAndRepair key="maintenance" addLog={addLog} />,
    'Recycling': <Recycling key="recycling" addLog={addLog} />,
    'Demolition': <Demolition key="demolition" addLog={addLog} />,
    'Logs': <Logs key="logs" />,
    'Outputs': <Outputs key="outputs" addLog={addLog} />,
    'Results': <Outputs key="outputs" addLog={addLog} />,
  }

  const contentKey = Object.keys(CONTENT_MAP).find(k => k.toLowerCase() === activeNode.toLowerCase()) || activeNode;
  const content = CONTENT_MAP[contentKey] || null;

  const handleStateChange = React.useCallback((data) => {
    setProjectData(prev => {
      if (JSON.stringify(prev) === JSON.stringify(data)) return prev;
      return { ...prev, ...data };
    });
  }, [setProjectData]);

  if (!dataLoaded) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ height: '100vh', backgroundColor: 'var(--app-bg-main)' }}>
        <div className="spinner-border text-primary" role="status">
          <span className="visually-hidden">Loading project data...</span>
        </div>
      </div>
    );
  }

  return (
    <ProjectDataProvider
      key={projectId}
      projectId={projectId}
      initialData={projectData}
      onStateChange={handleStateChange}
    >
      <ProjectLayout
        projectId={projectId}
        activeNode={activeNode}
        setActiveNode={handleSetActiveNode}
        onBackToHome={() => {
          addLog("Project closed. Returning to home.");
          navigate('/');
        }}
        onNewProject={handleNewProject}
        onOpenProject={handleOpenProject}
        addLog={addLog}
        isLocked={isLocked}
        setIsLocked={setIsLocked}
        projectName={projectData?.name}
        projectData={projectData}
        onRenameProject={handleRenameProject}
        onExportProject={handleExportProject}
        saveState={saveState}
      >
        {content ? React.cloneElement(content, {
          logs,
          onClearLogs: handleClearLogs,
          isLocked: isLocked,
          projectData: projectData
        }) : <div className="p-4 text-muted fst-italic">Select a section from the sidebar to begin.</div>}
      </ProjectLayout>
    </ProjectDataProvider>
  )
}

function App() {
  const navigate = useNavigate();

  const [isLoggedIn, setIsLoggedIn] = useState(() => sessionStorage.getItem('isLoggedIn') === 'true')
  const [projectData, setProjectData] = useState(() => createDefaultProject())

  const [logs, setLogs] = useState(() => {
    const saved = localStorage.getItem('logs')
    return saved ? JSON.parse(saved) : []
  })
  const [userName, setUserName] = useState(() => sessionStorage.getItem('userName') || '')
  const [isLocked, setIsLocked] = useState(false)

  useEffect(() => {
    // Clear legacy localStorage keys to ensure new sessions launch on the Login page
    localStorage.removeItem('isLoggedIn');
    localStorage.removeItem('userName');

    // Check for active Appwrite session on mount if not logged in
    const checkSession = async () => {
      try {
        const user = await account.get();
        if (user) {
           setIsLoggedIn(true);
           setUserName(user.name || user.email.split('@')[0]);
           sessionStorage.setItem('isGuest', 'false');
        }
      } catch (e) {
        // No active session
      }
    };
    if (!isLoggedIn) checkSession();

    // Offline sync hooks
    const handleOnline = () => {
      console.log("Internet restored. Triggering background sync...");
      projectStorageService.syncPendingProjects();
    };
    window.addEventListener('online', handleOnline);

    const syncInterval = setInterval(() => {
      projectStorageService.syncPendingProjects();
    }, 60000); // 60 seconds

    return () => {
      window.removeEventListener('online', handleOnline);
      clearInterval(syncInterval);
    };
  }, []);

  useEffect(() => { sessionStorage.setItem('isLoggedIn', isLoggedIn); }, [isLoggedIn]);
  useEffect(() => { sessionStorage.setItem('userName', userName); }, [userName]);

  useEffect(() => { localStorage.setItem('logs', JSON.stringify(logs)); }, [logs]);

  const [userSettings, setUserSettings] = useState(() => {
    const saved = localStorage.getItem('userSettings');
    return saved ? JSON.parse(saved) : {
      appearanceMode: 'Auto(follow os)',
      lightTheme: 'standard light',
      darkTheme: 'Dracula'
    };
  });

  useEffect(() => {
    localStorage.setItem('userSettings', JSON.stringify(userSettings));
  }, [userSettings]);

  const [isDarkMode, setIsDarkMode] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    return false;
  });

  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    const updateTheme = () => {
      if (userSettings.appearanceMode === 'dark') {
        setIsDarkMode(true);
      } else if (userSettings.appearanceMode === 'light') {
        setIsDarkMode(false);
      } else {
        setIsDarkMode(mediaQuery.matches);
      }
    };

    updateTheme();

    const handleChange = (e) => {
      if (userSettings.appearanceMode === 'Auto(follow os)') {
        setIsDarkMode(e.matches);
      }
    };
    if (mediaQuery.addEventListener) mediaQuery.addEventListener('change', handleChange);
    else mediaQuery.addListener(handleChange);
    return () => {
      if (mediaQuery.removeEventListener) mediaQuery.removeEventListener('change', handleChange);
      else mediaQuery.removeListener(handleChange);
    };
  }, [userSettings.appearanceMode]);

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute('data-bs-theme', isDarkMode ? 'dark' : 'light');

    if (isDarkMode) {
      if (userSettings.darkTheme === 'Dracula') {
        root.style.setProperty('--app-bg-main', '#282A36');
        root.style.setProperty('--app-bg-card', '#21222C');
        root.style.setProperty('--app-bg-alt', '#383A4A');
        root.style.setProperty('--app-border-mid', '#44475A');
        root.style.setProperty('--app-primary-accent', '#BD93F9');
        root.style.setProperty('--app-brand', '#90AF13');
        root.style.setProperty('--app-surface-pressed', '#565869');
        root.style.setProperty('--app-text-primary', '#F8F8F2');
        root.style.setProperty('--app-text-secondary', '#CED4ED');
        root.style.setProperty('--app-text-disabled', '#94A1D3');
        root.style.setProperty('--app-success', '#50FA7B');
        root.style.setProperty('--app-warning', '#FFB86C');
        root.style.setProperty('--app-danger', '#FF5555');
        root.style.setProperty('--app-info', '#8BE9FD');
      } else if (userSettings.darkTheme === 'Neon city standard dark') {
        root.style.setProperty('--app-bg-main', '#0C0F17');
        root.style.setProperty('--app-bg-card', '#121622');
        root.style.setProperty('--app-bg-alt', '#1A2030');
        root.style.setProperty('--app-border-mid', '#242B3D');
        root.style.setProperty('--app-primary-accent', '#E93CFF');
        root.style.setProperty('--app-brand', '#00D4FF');
        root.style.setProperty('--app-surface-pressed', '#2F3750');
        root.style.setProperty('--app-text-primary', '#E8ECF8');
        root.style.setProperty('--app-text-secondary', '#CDD4E5');
        root.style.setProperty('--app-text-disabled', '#6B738A');
        root.style.setProperty('--app-success', '#2EE6A6');
        root.style.setProperty('--app-warning', '#FFB020');
        root.style.setProperty('--app-danger', '#FF4D6D');
        root.style.setProperty('--app-info', '#3DA9FC');
      } else {
        root.style.setProperty('--app-bg-main', '#0F172A');
        root.style.setProperty('--app-bg-card', '#111827');
        root.style.setProperty('--app-bg-alt', '#1F2937');
        root.style.setProperty('--app-border-mid', '#374151');
        root.style.setProperty('--app-primary-accent', '#3B82F6');
        root.style.setProperty('--app-brand', '#2563EB');
        root.style.setProperty('--app-surface-pressed', '#4B5563');
        root.style.setProperty('--app-text-primary', '#E5E7EB');
        root.style.setProperty('--app-text-secondary', '#D1D5DB');
        root.style.setProperty('--app-text-disabled', '#6B7280');
        root.style.setProperty('--app-success', '#22C55E');
        root.style.setProperty('--app-warning', '#F59E0B');
        root.style.setProperty('--app-danger', '#EF4444');
        root.style.setProperty('--app-info', '#38BDF8');
      }
    } else {
      if (userSettings.lightTheme === 'soft pink') {
        root.style.setProperty('--app-bg-main', '#FDF2F8');
        root.style.setProperty('--app-bg-card', '#FFFFFF');
        root.style.setProperty('--app-bg-alt', '#FCE7F3');
        root.style.setProperty('--app-border-mid', '#FBCFE8');
        root.style.setProperty('--app-primary-accent', '#D94680');
        root.style.setProperty('--app-brand', '#EC4899');
        root.style.setProperty('--app-surface-pressed', '#F9A8D4');
        root.style.setProperty('--app-text-primary', '#4A044E');
        root.style.setProperty('--app-text-secondary', '#6B2155');
        root.style.setProperty('--app-text-disabled', '#A78B9C');
        root.style.setProperty('--app-success', '#22C55E');
        root.style.setProperty('--app-warning', '#F97316');
        root.style.setProperty('--app-danger', '#EF4444');
        root.style.setProperty('--app-info', '#3B82F6');
      } else if (userSettings.lightTheme === 'soft light') {
        root.style.setProperty('--app-bg-main', '#EFF1F5');
        root.style.setProperty('--app-bg-card', '#FFFFFF');
        root.style.setProperty('--app-bg-alt', '#E6E9EF');
        root.style.setProperty('--app-border-mid', '#CCD0DA');
        root.style.setProperty('--app-primary-accent', '#86A022');
        root.style.setProperty('--app-brand', '#90AF13');
        root.style.setProperty('--app-surface-pressed', '#DCE0E8');
        root.style.setProperty('--app-text-primary', '#4C4F69');
        root.style.setProperty('--app-text-secondary', '#6C6F85');
        root.style.setProperty('--app-text-disabled', '#9CA0B0');
        root.style.setProperty('--app-success', '#22C55E');
        root.style.setProperty('--app-warning', '#F97316');
        root.style.setProperty('--app-danger', '#EF4444');
        root.style.setProperty('--app-info', '#3B82F6');
      } else {
        root.style.setProperty('--app-bg-main', '#F8FAFC');
        root.style.setProperty('--app-bg-card', '#FFFFFF');
        root.style.setProperty('--app-bg-alt', '#F1F5F9');
        root.style.setProperty('--app-border-mid', '#E2E8F0');
        root.style.setProperty('--app-primary-accent', '#2563EB');
        root.style.setProperty('--app-brand', '#1D4ED8');
        root.style.setProperty('--app-surface-pressed', '#CBD5E1');
        root.style.setProperty('--app-text-primary', '#0F172A');
        root.style.setProperty('--app-text-secondary', '#475569');
        root.style.setProperty('--app-text-disabled', '#94A3B8');
        root.style.setProperty('--app-success', '#16A34A');
        root.style.setProperty('--app-warning', '#F59E0B');
        root.style.setProperty('--app-danger', '#DC2626');
        root.style.setProperty('--app-info', '#0284C7');
      }
    }
  }, [isDarkMode, userSettings]);

  const addLog = (message) => {
    const time = new Date().toTimeString().split(' ')[0]
    setLogs(prev => [...prev, `[${time}] ${message}`])
  }

  const handleLogin = (isGuest = false, name = "Admin") => {
    setIsLoggedIn(true)
    setUserName(name)
    sessionStorage.setItem('isGuest', isGuest)
    addLog(isGuest ? `Guest user '${name}' logged in.` : `User '${name}' logged in.`)
    navigate('/')
  }

  const handleLogout = async () => {
    const isGuest = sessionStorage.getItem('isGuest') === 'true';
    if (!isGuest) {
      try {
        await account.deleteSession('current');
      } catch (e) {
        console.error('Logout error', e);
      }
    }
    setIsLoggedIn(false);
    sessionStorage.removeItem('isGuest');
    addLog('Logged out successfully.');
    navigate('/login');
  };

  const handleAdminLogin = async (credentials) => {
    try {
        if (credentials.action === 'signup') {
            await account.create(ID.unique(), credentials.email, credentials.password, credentials.name);
            await account.createEmailPasswordSession(credentials.email, credentials.password);
            const user = await account.get();
            handleLogin(false, user.name || credentials.email.split('@')[0]);
        } else {
            await account.createEmailPasswordSession(credentials.email, credentials.password);
            const user = await account.get();
        }
    } catch (e) {
        console.error("Auth error:", e);
        throw e; // Throw to be handled by Loginpage
    }
  };

  const handleGoogleLogin = () => {
    account.createOAuth2Session(
        'google',
        window.location.origin, // Success URL (goes back to Homepage, which triggers checkSession)
        window.location.origin + '/login' // Failure URL
    );
  };

  const handleProjectCreate = (creationData) => {
    const newProjectId = 'new_project_' + Date.now();
    setProjectData(buildProjectFromCreation(creationData));
    setLogs([]);
    setIsLocked(false);
    addLog(`New project '${creationData?.name || 'New Project'}' created.`);
    navigate(`/project/${newProjectId}/General Information`);
    return { id: newProjectId, name: creationData.name };
  };

  const handleProjectOpen = async (projectId = 'default_project', projectName = 'Default Project') => {
    const saved = await projectStorageService.loadProject(projectId);
    if (saved) {
      try {
        setProjectData(normalizeProjectData(saved));
      } catch (e) {
        console.error('Failed to load project', e);
      }
    } else if (projectName) {
      setProjectData(prev => normalizeProjectData({ ...prev, name: projectName }));
    }
    navigate(`/project/${projectId}/General Information`);
    addLog(`Project '${projectName}' opened successfully.`);
  };

  return (
    <Routes>
      <Route path="/login" element={
        isLoggedIn ? <Navigate to="/" replace /> : <Loginpage onLogin={handleAdminLogin} onGuestLogin={(name) => handleLogin(true, name || 'Guest')} onGoogleLogin={handleGoogleLogin} />
      } />

      <Route path="/" element={
        <ProtectedRoute isLoggedIn={isLoggedIn}>
          <HomePage
            onProjectOpen={handleProjectOpen}
            onProjectCreate={handleProjectCreate}
            userName={userName}
            isDarkMode={isDarkMode}
            userSettings={userSettings}
            setUserSettings={setUserSettings}
            onLogout={handleLogout}
          />
        </ProtectedRoute>
      } />

      <Route path="/project/:projectId/:nodeId?" element={
        <ProtectedRoute isLoggedIn={isLoggedIn}>
          <ProjectViewWrapper
            projectData={projectData}
            setProjectData={setProjectData}
            logs={logs}
            setLogs={setLogs}
            isLocked={isLocked}
            setIsLocked={setIsLocked}
            addLog={addLog}
          />
        </ProtectedRoute>
      } />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
