
from pylatex import NoEscape

APPENDIX_B_LATEX = r"""
\newpage
\section*{\fontsize{14pt}{16pt}\selectfont\bfseries Appendix B: Calculation Methodology}
\addcontentsline{toc}{section}{Appendix B: Calculation Methodology}

\noindent
This chapter presents the calculation method and equations used for cost calculations.
The glossary for the terms used in the equations are mentioned below.

\vspace{0.5em}

\begin{itemize}
\item $A_{Di}$ = Accident distribution
\item $A_{Ne}$ = Number of accidents for each vehicle type
\item $A_{Tn}$ = Total number of accidents in the stipulated time
\item $C_{Di}$ = Distance related cost
\item $CF_D$ = Distance related congestion factor
\item $CF_T$ = Time related congestion factor
\item $C_{Ti}$ = Time related cost
\item $DC_m$ = Duration of construction in months
\item $D_{ma}$ = Number of equipment usage days
\item $D_{wm}$ = Number of working days in a month
\item $Di$ = Distance travelled for transportation of material
\item $EF_m$ = Emission factor for materials
\item $EF_{ma}$ = Emission factor for energy consumption
\item $EF_{tp}$ = Emission factor for transportation
\item $EF_v$ = Vehicular emission factor
\item $E_{VD}$ = Vehicle damage cost
\item $E_{Vi}$ = Economic cost of injury
\item $Q_{rm}$ = Quantity of recycle material
\item $RE_c$ = Recycling cost
\item $T_{AT}$ = Additional travel time
\item $T_{VP}$ = Time value
\item $V/C$ = Volume-Capacity ratio
\item $V_{CD}$ = Vehicle counts per day
\item $\mathrm{AC}$ = Accident cost
\item $\mathrm{CC}$ = Cargo capacity
\item $\mathrm{CFU}$ = Price of fuel
\item $\mathrm{CHC}$ = Commodity holding cost
\item $\mathrm{COF}$ = Conversion factor
\item $\mathrm{CR}$ = Crash rate
\item $\mathrm{CW}$ = Crew cost
\item $\mathrm{DC}$ = Depreciation cost
\item $\mathrm{D_{cf}}$ = Demolition and disposal cost
\item $\mathrm{D_{cr}}$ = Demolition and disposal cost for reconstruction
\item $\mathrm{DC_{y}}$ = Duration of construction (years)
\item $\mathrm{DF_{EC}}$ = Emission cost for end-of-life demolition
\item $\mathrm{DR_{EC}}$ = Emission cost for demolition during reconstruction
\item $\mathrm{EOL}$ = Engine oil consumption
\item $\mathrm{EOLC}$ = Engine oil cost
\item $\mathrm{EOL_{P}}$ = Engine oil price
\item $\mathrm{F_{C}}$ = Fuel cost
\item $\mathrm{FC_{CB}}$ = Fuel consumption petrol
\item $\mathrm{FC_{CS}}$ = Fuel consumption diesel
\item $\mathrm{FL}$ = Fall
\item $\mathrm{FXC}$ = Fixed cost
\item $\mathrm{G}$ = Grease consumption
\item $\mathrm{GC}$ = Grease cost
\item $\mathrm{G_{P}}$ = Grease price
\item $I$ = Interest rate
\item $\mathrm{IC}$ = Initial construction cost
\item $\mathrm{IR}$ = Investment ratio
\item $\mathrm{LC}$ = Maintenance labour cost
\item $\mathrm{MIc}$ = Major inspection cost
\item $\mathrm{MR_{c}}$ = Major repair cost
\item $\mathrm{MR_{EC}}$ = Major repair emission cost
\item $n$ = Design life (years)
\item $\mathrm{NP}$ = New vehicle cost
\item $\mathrm{O_{Avg}}$ = Average occupancy of a vehicle
\item $\mathrm{OL}$ = Other oil consumption
\item $\mathrm{OLC}$ = Other oil cost
\item $\mathrm{OL_{P}}$ = Other oil price
\item $\mathrm{P_{IC}}$ = Percentage of initial construction cost
\item $\mathrm{P_{IEC}}$ = Percentage of initial carbon emission
\item $\mathrm{PMc}$ = Periodic maintenance cost
\item $\mathrm{PM_{EC}}$ = Periodic maintenance emission cost
\item $\mathrm{PT}$ = Passenger time cost
\item $\mathrm{PWF}$ = Present Worth Factor
\item $\mathrm{PWR}$ = Power weight ratio
\item $Q$ = Quantity of material
\item $r$ = Discount rate
\item $R$ = Rate of material
\item $\mathrm{RC_{BE}}$ = Replacement cost of bearing and expansion joint
\item $\mathrm{RCN}$ = Reconstruction cost
\item $\mathrm{RD}$ = Rerouting distance
\item $\mathrm{REC_{EC}}$ = Reconstruction emission cost
\item $\mathrm{RG}$ = Roughness
\item $\mathrm{RI_{c}}$ = Routine inspection cost 
\item $\mathrm{R}$ = Rate of recycle material
\item $\mathrm{RS}$ = Rise
\item $\mathrm{RUC}$ = Road user cost
\item $\mathrm{SP}$ = Spare part cost
\item $\mathrm{TC}$ = Time cost
\item $\mathrm{TYC}$ = Tyre cost
\item $\mathrm{TCe}$ = Cost of each tyre
\item $\mathrm{TCR}$ = Time cost for reconstruction
\item $\mathrm{TL}$ = Tyre life
\item $\mathrm{TN}$ = Number of tyres
\item $\mathrm{UPD}$ = Utilization per day
\item $\mathrm{VOC}$ = Vehicle operating cost
\item $\mathrm{VOT}$ = Value of time cost
\item $\mathrm{W}$ = Width of carriageway
\item $\mathrm{WPI}$ = Wholesale price index
\item $\mathrm{WZM}$ = Work zone multiplier
\item $x$ = Periodic interval (years)
\item $\mathrm{ADT}$ = Average daily traffic
\item $\mathrm{IEC}$ = Initial emission cost
\item $\mathrm{IAEC}$ = Initial carbon emission cost from on-site activities
\item $\mathrm{IETC}$ = Initial carbon emission cost due to transportation of material
\item $\mathrm{SCC}$ = Social cost of carbon
\item $\mathrm{VEC}$ = Vehicular emission cost
\item $\mathrm{IAEC}$ = Initial on-site emission cost
\item $\mathrm{ECR}$ = Energy consumption rate
\item $H$ = Average machinery hours per day
\item $D_{ma}$ = Number of equipment usage days
\item $EF_{ma}$ = Emission factor for machinery energy use
\end{itemize}

\vspace{0.5em}

{\fontsize{13pt}{15pt}\selectfont\bfseries B.1 Initial Cost}
\addcontentsline{toc}{subsection}{B.1 Initial Cost}

\vspace{0.3em}
\textbf{B.1.1 Economic cost}
\addcontentsline{toc}{subsubsection}{B.1.1 Economic cost}

\noindent
Initial construction cost
\[
IC = \sum_{i=1}^{n} Q_i \times R_i
\]

\noindent
Time cost
\[
TC = IC \times I \times DC_y \times IR
\]

\vspace{0.3em}
\textbf{B.1.2 Social cost}
\addcontentsline{toc}{subsubsection}{B.1.2 Social cost}

\noindent
Road user cost during construction
\[
RUC_{cn} = VOC_{cn} + VOT_{cn} + AC_{cn}
\]
\[
\resizebox{\linewidth}{!}{$\displaystyle
VOC_{cn} = D_{wm} \times DC_m \times RD \times
\left[
  \sum_{j=1}^{o} \left\{ (C_{Ti})_{j} \times (V_{CD})_{j} \times (CF_{T})_{j} \times (WPI_{Ti})_{j} \right\}
  + \sum_{k=1}^{p} \left\{ (C_{Di})_{k} \times (V_{CD})_{k} \times (CF_{D})_{k} \times (WPI_{Di})_{k} \right\}
\right]
$}
\]

\noindent
Distance related costs
\[
F_{Cp} = CFU_{Pe} \times FC_{CS}
\]
\[
F_{Cd} = CFU_{Di} \times FC_{CB}
\]
\[
F_{C} = CFU \times FC
\]

\begin{table}[H]
\centering
\caption*{\textit{Table B-1 Fuel Consumption equations for different vehicles}}
{\fontsize{9pt}{11pt}\selectfont
\everymath{\fontsize{9pt}{11pt}\selectfont}
\everydisplay{\fontsize{9pt}{11pt}\selectfont}
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{2.80}
\begin{tabular}{|p{3cm}|p{13.5cm}|}
\hline
Small and Big Car &
\makebox[\linewidth][c]{$
\begin{aligned}
FC_{CS} &= 30 + \frac{844.085}{V} + 0.003V^2 + (0.001 \times RG) + (0.3414 \times RS) - (0.2225 \times FL) \\
FC_{CB} &= 35 + \frac{983.503}{V} + 0.003V^2 + (0.002 \times RG) + (0.339 \times RS) - (0.4785 \times FL)
\end{aligned}
$} \\ \hline
Two-wheeler &
\makebox[\linewidth][c]{$FC = 2.704 + \frac{439.656}{V} + 0.00349V^2 + (0.000157 \times RG) + (0.3642 \times RS) - (0.2709 \times FL)$} \\ \hline
Buses &
\makebox[\linewidth][c]{$FC = 34.23 + \frac{4054.42}{V} + 0.02149V^2 + (0.001246 \times RG) + (3.4557 \times RS) - (1.8454 \times FL)$} \\ \hline
LCV &
\makebox[\linewidth][c]{$FC_{CB} = 22.504 + \frac{1708.244}{V} + 0.02591V^2 + (0.001612 \times RG) + (5.6863 \times RS) - (0.8744 \times FL)$} \\ \hline
HCV &
\makebox[\linewidth][c]{$FC_{CB} = 50.0 + \frac{8049.955}{V} + 0.012V^2 + (0.005 \times RG) + (4.565 \times RS) - (4.904 \times FL) - (7.285 \times PWR)$} \\ \hline
MCV &
\makebox[\linewidth][c]{$FC_{CB} = 90.0 + \frac{14489.919}{V} + 0.0216V^2 + (0.01 \times RG) + (8.217 \times RS) - (8.8272 \times FL) - (13.113 \times PWR)$} \\ \hline
\end{tabular}
}
\end{table}

\begin{table}[H]
\centering
\caption*{\textit{Table B-2 Speed equations for different vehicles}}
{\fontsize{9pt}{11pt}\selectfont
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{1.9}
\begin{tabular}{|p{3cm}|p{13.5cm}|}
\hline
Small Car & \makebox[13.5cm][c]{$V = 81.19 - (0.7892 \times RF) - [0.001891 \times (RG - 2000)]$} \\ \hline
Big Car & \makebox[13.5cm][c]{$V = 81.92 - (0.7963 \times RF) - [0.001915 \times (RG - 2000)]$} \\ \hline
Two-wheeler & \makebox[13.5cm][c]{$V = 59.71 - (0.7892 \times RF) - [0.001891 \times (RG - 2000)]$} \\ \hline
Buses & \makebox[13.5cm][c]{$V = 54.23 - (0.4111 \times RF) - [0.00098 \times (RG - 2000)]$} \\ \hline
LCV & \makebox[13.5cm][c]{$V = 57.41 - (0.5119 \times RF) - [0.00102 \times (RG - 2000)]$} \\ \hline
HCV & \makebox[13.5cm][c]{$V = 96.52 - (0.5040 \times RF) - [0.00100 \times (RG - 2000)]$} \\ \hline
MCV & \makebox[13.5cm][c]{$V = 44.79 - (0.3994 \times RF) - [0.00079 \times (RG - 2000)]$} \\ \hline
\end{tabular}
}
\end{table}
\begin{center}
\textcolor{red}{\textit{(Note: This table of equation is only for two lane road)}}
\end{center}

\[
SP = \frac{SP}{NP} \times NP
\]

\begin{table}[H]
\centering
\caption*{\textit{Table B-3 Spare part to New vehicle cost ratio for different vehicles}}
{\fontsize{9pt}{11pt}\selectfont
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{1.9}
\begin{tabular}{|p{3cm}|p{13.5cm}|}
\hline
Small Car & \makebox[13.5cm][c]{$\frac{SP}{NP} = 0.0075 \times (RG - 2000) \times 10^{-5}$} \\ \hline
Big Car & \makebox[13.5cm][c]{$\frac{SP}{NP} = 0.0045 \times (RG - 2000) \times 10^{-5}$} \\ \hline
Two-wheeler & \makebox[13.5cm][c]{$\frac{SP}{NP} = [-55.879 + (0.024 \times RG)] \times 10^{-5}$} \\ \hline
Buses & \makebox[13.5cm][c]{$\frac{SP}{NP} = e^{-9.7871 + (0.007373 \times RF) + (0.0000723 \times RG) + \frac{1.925}{W}}$} \\ \hline
LCV & \makebox[13.5cm][c]{$\frac{SP}{NP} = e^{-10.5615 + (0.000141 \times RG) + \frac{3.493}{W}}$} \\ \hline
HCV and MCV & \makebox[13.5cm][c]{$\frac{SP}{NP} = e^{-9.492638 + (0.0001413 \times RG) + \frac{3.493}{W}}$} \\ \hline
\end{tabular}
}
\end{table}

\[
LC = a \times SP
\]
\textit{a for small car and big car = 1.79934, Two-wheeler = 0.5498, Buses = 1.1781, LCV = 0.85773, HCV and MCV = 0.7912}

\[
TC = \frac{TC_e \times TN}{TL}
\]

\begin{table}[H]
\centering
\caption*{\textit{Table B-4 Tyre Life equations for different vehicles}}
{\fontsize{9pt}{11pt}\selectfont
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{1.9}
\begin{tabular}{|p{3cm}|p{13.5cm}|}
\hline
Small and big car & \makebox[13.5cm][c]{$TL = 68771 - (147.9 \times RF) - (26.72 \times RG/W)$} \\ \hline
Two-wheeler & \makebox[13.5cm][c]{$TL = 47340 - (101.8 \times RF) - (18.39 \times RG/W)$} \\ \hline
Buses & \makebox[13.5cm][c]{$TL = 38519 - (389.52 \times RF) - (1.32 \times RG) + (983.829 \times W)$} \\ \hline
LCV & \makebox[13.5cm][c]{$TL = 22382 - (375.3 \times RF) - (1.037 \times RG) + (3817 \times W)$} \\ \hline
HCV & \makebox[13.5cm][c]{$TL = 24662 - (413.6 \times RF) - (1.142 \times RG) + (4205 \times W)$} \\ \hline
MCV & \makebox[13.5cm][c]{$TL = 23726 - (398 \times RF) - (1.0099 \times RG) + (4046 \times W)$} \\ \hline
\end{tabular}
}
\end{table}

\[
EOLC = EOL \times EOL_{P} \times 10^{-3}
\]

\begin{table}[H]
\centering
\caption*{\textit{Table B-5 Engine oil consumption for different vehicles}}
{\fontsize{9pt}{11pt}\selectfont
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{1.9}
\begin{tabular}{|p{3cm}|p{13.5cm}|}
\hline
Small and big car & \makebox[13.5cm][c]{$EOL = 1.8807 + (0.036615 \times RF) + (0.000578 \times RG/W)$} \\ \hline
Two-wheeler & \makebox[13.5cm][c]{$EOL = 0.405 + (0.007899 \times RF) + (0.000125 \times RG/W)$} \\ \hline
Buses & \makebox[13.5cm][c]{$EOL = 0.4303 + (0.001494 \times RF) + (0.0007885 \times RG/W)$} \\ \hline
LCV & \makebox[13.5cm][c]{$EOL = 0.80679 + (0.019496 \times RF) + (0.0001297 \times RG/W)$} \\ \hline
HCV & \makebox[13.5cm][c]{$EOL = 1.0277 + (0.02495 \times RF) + (0.0001782 \times RG/W)$} \\ \hline
MCV & \makebox[13.5cm][c]{$EOL = 1.3826 + (0.03348 \times RF) + (0.002319 \times RG/W)$} \\ \hline
\end{tabular}
}
\end{table}

\[
OLC = OL \times OLP \times 10^{-4}
\]

\begin{table}[H]
\centering
\caption*{\textit{Table B-6 Other oil consumption equations for different vehicles}}
{\fontsize{9pt}{11pt}\selectfont
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{1.9}
\begin{tabular}{|p{3cm}|p{13.5cm}|}
\hline
Small and big car and two-wheeler & \makebox[13.5cm][c]{$OL = 1.631 + (0.05167 \times RF) + (0.001867 \times RG/W)$} \\ \hline
Buses & \makebox[13.5cm][c]{$OL = 3.3201 + (0.002889 \times RF) + (0.0008217 \times RG) - (0.3295 \times W)$} \\ \hline
LCV & \makebox[13.5cm][c]{$OL = 2.0415 + (0.0001058 \times RG)$} \\ \hline
HCV and MCV & \makebox[13.5cm][c]{$OL = 5.1037 + (0.0002646 \times RG)$} \\ \hline
\end{tabular}
}
\end{table}

\[
GC = G \times G_{P} \times 10^{4}
\]

\begin{table}[H]
\centering
\caption*{\textit{Table B-7 Grease consumption equations for different vehicles}}
{\fontsize{9pt}{11pt}\selectfont
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{1.9}
\begin{tabular}{|p{3cm}|p{13.5cm}|}
\hline
Small car, big car and two-wheeler & \makebox[13.5cm][c]{$G = 2.816 + (0.2007 \times RF)$} \\ \hline
Buses & \makebox[13.5cm][c]{$G = 4.992 + (0.03376 \times RF) + (0.3634 \times W)$} \\ \hline
LCV & \makebox[13.5cm][c]{$G = 0.3661 + (0.0283 \times RF) + (0.000251 \times RG)$} \\ \hline
HCV and MCV & \makebox[13.5cm][c]{$G = 0.9153 + (0.0707 \times RF) + (0.000627 \times RG)$} \\ \hline
\end{tabular}
}
\end{table}

\textbf{Time related costs}

\[
FXC = \frac{b}{UPD}
\]
\textit{b for small car and big car = 395.65, Two-wheeler = 24.32, Buses = 772.89, LCV = 723.80, HCV = 924.28, MCV = 1238.26}

\begin{table}[H]
\centering
\caption*{\textit{Table B-8 Utilization per day equations for different vehicles}}
{\fontsize{9pt}{11pt}\selectfont
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{1.9}
\begin{tabular}{|p{3cm}|p{13.5cm}|}
\hline
Small car & \makebox[13.5cm][c]{$UPD = 6.7127 \times V$} \\ \hline
Big Car & \makebox[13.5cm][c]{$UPD = 6.7378 \times V$} \\ \hline
Two-wheeler & \makebox[13.5cm][c]{$UPD = 2.119 \times V$} \\ \hline
Buses & \makebox[13.5cm][c]{$UPD = 22.7134 + (12.2569 \times V)$} \\ \hline
LCV & \makebox[13.5cm][c]{$UPD = 28.807 + (2.1836 \times V)$} \\ \hline
HCV & \makebox[13.5cm][c]{$UPD = 55.6719 + (4.22 \times V)$} \\ \hline
MCV & \makebox[13.5cm][c]{$UPD = 77.7233 + (5.8915 \times V)$} \\ \hline
\end{tabular}
}
\end{table}

\[
DC = \frac{c}{UPD}
\]
\textit{c for small and big cars = 42.83, Two-wheeler = 4.26, Buses = 221, LCV = 120.9, HCV = 154.54 and MCV = 238.54}

For Car and Two wheelers,
\[
PT = \frac{d}{V}
\]

For Buses,
\[
PT = \frac{d}{UPD}
\]
\textit{d for small and big car = 328.06, Two-wheeler = 70.29, Buses = 15509.8}

\textcolor{red}{\textit{(Note: This equation is only for two lane road)}}

\[
CW = \frac{e}{UPD}
\]
\textit{e for Buses = 3775.3, LCV = 900, HCV = 1500 and MCV = 1800}

\[
CHC = \frac{f}{UPD}
\]
\textit{f for LCV = 71.35, HCV = 218.75, MCV = 409.28}

\textcolor{red}{\textit{(Note: This equation is only for two lane road)}}

\textbf{Time related congestion factors}

\begin{table}[H]
\centering
\caption*{\textit{Table B-9 Time related congestion factor equations for different vehicles}}
{\fontsize{9pt}{11pt}\selectfont
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{1.9}
\begin{tabular}{|p{3cm}|p{13.5cm}|}
\hline
Cars & \makebox[13.5cm][c]{$CF_T = 1.087 + (0.483 \times V/C)$} \\ \hline
Two-wheelers & \makebox[13.5cm][c]{$CF_T = 0.804 + (0.865 \times V/C)$} \\ \hline
Buses & \makebox[13.5cm][c]{$CF_T = 0.864 + (0.543 \times V/C)$} \\ \hline
LCV & \makebox[13.5cm][c]{$CF_T = 0.925 + (0.573 \times V/C)$} \\ \hline
HCV and MCV & \makebox[13.5cm][c]{$CF_T = 0.878 + (0.561 \times V/C)$} \\ \hline
\end{tabular}
}
\end{table}
\begin{center}
 \textcolor{red}{\textit{(Note: This equation is only for two lane road)}}   
\end{center}


\textbf{Distance related congestion factor}

\begin{table}[H]
\centering
\caption*{\textit{Table B-10 Distance related congestion factor equations for different vehicles }}
{\fontsize{9pt}{11pt}\selectfont
\setlength{\tabcolsep}{6pt}
\renewcommand{\arraystretch}{1.9}
\begin{tabular}{|p{3cm}|p{13.5cm}|}
\hline
Cars & \makebox[13.5cm][c]{$CF_D = 0.893 + (0.259 \times V/C)$} \\ \hline
Two-wheelers & \makebox[13.5cm][c]{$CF_D = 0.917 + (0.112 \times V/C)$} \\ \hline
Buses & \makebox[13.5cm][c]{$CF_D = 0.800 + (1.1 \times V/C)$} \\ \hline
LCV & \makebox[13.5cm][c]{$CF_D = 0.9 + (1.0 \times V/C)$} \\ \hline
HCV & \makebox[13.5cm][c]{$CF_D = 0.925 + (0.482 \times V/C)$} \\ \hline
MCV & \makebox[13.5cm][c]{$CF_D = 0.900 + (1.4 \times V/C)$} \\ \hline
\end{tabular}
}
\end{table}
\begin{center}
    \textcolor{red}{\textit{(Note: This equation is only for two lane road)}}
\end{center}


\[
\resizebox{\linewidth}{!}{$\displaystyle
VOT_{cn} = D_{wm} \times DC_m \times T_{AT} \times
\left[
  \sum_{j=1}^{o} \left\{ (T_{VP})_{j} \times (V_{CD})_{j} \times (O_{Avg})_{j} \times (WPI_{Ti})_{j} \right\}
  + \sum_{k=1}^{p} \left\{ (CHC_{T})_{k} \times (V_{CD})_{k} \times (WPI_{Di})_{k} \right\}
\right]
$}
\]

\[
\resizebox{\linewidth}{!}{$\displaystyle
AC_{cn} = A_{Tn} \times
\left[
  \sum_{j=1}^{o} \left\{ (E_{Vi})_{j} \times (A_{Di})_{j} \times (WPI_{me})_{j} \right\}
  + \sum_{k=1}^{p} \left\{ (E_{VD})_{k} \times (A_{Ne})_{k} \times (WPI_{sp})_{k} \right\}
\right]
$}
\]

\[
A_{Tn} = D_{wm} \times DC_m \times CR \times WZM \times RD \times 10^{-6}
\]

\vspace{0.5em}

\section*{\fontsize{14pt}{16pt}\selectfont\bfseries B.1.3 Environmental cost}
\addcontentsline{toc}{subsubsection}{B.1.3 Environmental cost}

\begin{itemize}
\item Embodied carbon emission cost during construction
\[
IEC = SCC \times \sum_{j=1}^{o} \left[ Q_{j} \times (COF)_{j} \times (EF_{m})_{j} \right]
\]

\item Vehicular emission cost during construction due to rerouting
\[
VEC = SCC \times D_{wm} \times DC_m \times RD \times \sum_{k=1}^{p} \left[ ADT_{k} \times (EF_{v})_{k} \right]
\]

\item Carbon emissions from on-site activities during construction
\[
IAEC = SCC \times \sum_{j=1}^{o} \left[ (ECR)_{j} \times (H)_{j} \times (D_{ma})_{j} \times (EF_{ma})_{j} \right]
\]

\item Carbon emission cost due to transportation of construction material
\[
IETC = SCC \times \sum_{j=1}^{o} \left[ Q_{j} \times Di_{j} \times (EF_{tp})_{j} \right]
\]
\end{itemize}

%----------------------------------------------
{\fontsize{13pt}{15pt}\selectfont\bfseries B.2 Use Stage Cost}
\addcontentsline{toc}{subsection}{B.2 Use Stage Cost}

\vspace{0.3em}
\textbf{B.2.1 Economic cost}
\addcontentsline{toc}{subsubsection}{B.2.1 Economic cost}

\begin{itemize}
  \item \textbf{Routine Inspection cost}
    \[ RI_c = \mathrm{PWF} \times P_{Ics} \]
    \[
\mathrm{PWF} = \sum_{i=1}^{\mathrm{int}\left(\frac{n}{x}\right)-1} \frac{(1+f)^{i x}}{(1+r)^{i x}}
\]
  \item \textbf{Periodic maintenance cost}
    \[ PM_c = \mathrm{PWF} \times P_{ICm} \]
  \item \textbf{Major repair cost}
    \[ MR_c = \mathrm{PWF} \times P_{ICr} \]
  \item \textbf{Major inspection cost}
    \[ MI_c = \mathrm{PWF} \times P_{ICi} \]
  \item \textbf{Replacement cost of bearings and expansion joints}
    \[ RC_{BE} = \mathrm{PWF} \times P_{SCr} \]
\end{itemize}




\vspace{0.3em}
\textbf{B.2.2 Social cost}
\addcontentsline{toc}{subsubsection}{B.2.2 Social cost}

\begin{itemize}
  \item \textbf{Road user cost due to rerouting during major repairs}
    \[ RUC_{mr} = VOC_{mr} + VOT_{mr} + AC_{mr} \]
    \[
    \resizebox{\linewidth}{!}{$\displaystyle
    VOC_{mr} = \mathrm{PWF} \times D_{wm} \times DC_m \times RD \left[
      \sum_{j=1}^{o} \left\{ (C_{Ti})_j \times (V_{CD})_j \times (CF_T)_j \times (WPI_{Ti})_j \right\}
      + \sum_{k=1}^{p} \left\{ (C_{Di})_k \times (V_{CD})_k \times (CF_D)_k \times (WPI_{Di})_k \right\}
    \right]
    $}
    \]
    (Refer to table B-1 to B-16 to calculate distance and time related costs for VOC)
    \[
    \resizebox{\linewidth}{!}{$\displaystyle
    VOT_{mr} = \mathrm{PWF} \times D_{wm} \times DC_m \times T_{AT} \left[
      \sum_{j=1}^{o} \left\{ (T_{VP})_j \times (V_{CD})_j \times (O_{Avg})_j \times (WPI_{Ti})_j \right\}
      + \sum_{k=1}^{p} \left\{ (CHC_T)_k \times (V_{CD})_k \times (WPI_{Di})_k \right\}
    \right]
    $}
    \]
    \[
    \resizebox{\linewidth}{!}{$\displaystyle
    AC_{mr} = \mathrm{PWF} \times A_{Tn} \left[
      \sum_{j=1}^{o} \left\{ (E_{Vi})_j \times (A_{Di})_j \times (WPI_{me})_j \right\}
      + \sum_{k=1}^{p} \left\{ (E_{VD})_k \times (A_{Ne})_k \times (WPI_{sp})_k \right\}
    \right]
    $}
    \]

  \item \textbf{Road user cost due to rerouting during major repairs}
    \[ RUC_{rbe} = VOC_{rbe} + VOT_{rbe} + AC_{rbe} \]
    \[
    \resizebox{\linewidth}{!}{$\displaystyle
    VOC_{rbe} = \mathrm{PWF} \times D_{wm} \times DC_m \times RD \left[
      \sum_{j=1}^{o} \left\{ (C_{Ti})_j \times (V_{CD})_j \times (CF_T)_j \times (WPI_{Ti})_j \right\}
      + \sum_{k=1}^{p} \left\{ (C_{Di})_k \times (V_{CD})_k \times (CF_D)_k \times (WPI_{Di})_k \right\}
    \right]
    $}
    \]
    (Refer to table B-1 to B-16 to calculate distance and time related costs for VOC)
    \[
    \resizebox{\linewidth}{!}{$\displaystyle
    VOT_{rbe} = \mathrm{PWF} \times D_{wm} \times DC_m \times T_{AT} \left[
      \sum_{j=1}^{o} \left\{ (T_{VP})_j \times (V_{CD})_j \times (O_{Avg})_j \times (WPI_{Ti})_j \right\}
      + \sum_{k=1}^{p} \left\{ (CHC_T)_k \times (V_{CD})_k \times (WPI_{Di})_k \right\}
    \right]
    $}
    \]
    \[
    \resizebox{\linewidth}{!}{$\displaystyle
    AC_{rbe} = \mathrm{PWF} \times A_{Tn} \left[
      \sum_{j=1}^{o} \left\{ (E_{Vi})_j \times (A_{Di})_j \times (WPI_{me})_j \right\}
      + \sum_{k=1}^{p} \left\{ (E_{VD})_k \times (A_{Ne})_k \times (WPI_{sp})_k \right\}
    \right]
    $}
    \]
\end{itemize}

\vspace{0.3em}
\textbf{B.2.3 Environmental cost}
\addcontentsline{toc}{subsubsection}{B.2.3 Environmental cost}

\begin{itemize}
  \item Carbon emission cost due to periodic maintenance
    \[ PM_{EC} = \mathrm{PWF} \times P_{IECp} \]
  \item Carbon emission cost due to major repairs
    \[ MR_{EC} = \mathrm{PWF} \times P_{IECm} \]
  \item Carbon emission due to rerouting of vehicles during major repairs
    \[
    VEC_{MR} = \mathrm{PWF} \times \mathrm{SCC} \times D_{wm} \times DC_m \times RD
    \times \sum_{k=1}^{p} \left[(ADT)_k \times (EF_v)_k\right]
    \]
  \item Carbon emission cost due to replacement of bearings and expansion joints
    \[ RC_{BEE} = \mathrm{PWF} \times P_{IESr} \]
  \item Carbon emission due to rerouting of vehicles during replacement of bearings and expansion joints
    \[
    VEC_{RE} = \mathrm{PWF} \times \mathrm{SCC} \times D_{wm} \times DC_m \times RD
    \times \sum_{k=1}^{p} \left[(ADT)_k \times (EF_v)_k\right]
    \]
\end{itemize}

%----------------------------------------------
{\fontsize{13pt}{15pt}\selectfont\bfseries B.3 End-of-Life Stage Cost Calculation}
\addcontentsline{toc}{subsection}{B.3 End-of-Life Stage Cost Calculation}

\vspace{0.3em}
\textbf{B.3.1 Economic cost}
\addcontentsline{toc}{subsubsection}{B.3.1 Economic cost}

\begin{itemize}
  \item \textbf{Demolition and disposal cost for reconstruction}
    \[ D_{cr} = \mathrm{PWF} \times P_{ICd} \]
  \item \textbf{Reconstruction cost}
    \[ \mathrm{RCN} = \mathrm{PWF} \times \mathrm{IC} \]
  \item \textbf{Time cost for reconstruction of bridge}
    \[ \mathrm{TCR} = \bigl| \mathrm{PWF} \times \mathrm{TC} \bigr| \]
  \item \textbf{Demolition cost at end of life}
    \[ D_{cf} = \mathrm{PWF} \times P_{ICd} \]
  \item \textbf{Recycling cost}
    \[ RE_c = \mathrm{PWF} \times \sum_{i=0}^{m} (RS)_i \times (Q_{rm})_i \]
\end{itemize}

\vspace{0.3em}
\textbf{B.3.2 Social cost}
\addcontentsline{toc}{subsubsection}{B.3.2 Social cost}

\begin{itemize}
  \item \textbf{Road user cost due to rerouting of vehicles during demolition for reconstruction}
    \[ \mathrm{RUC}_{dr} = \mathrm{VOC}_{dr} + \mathrm{VOT}_{dr} + \mathrm{AC}_{dr} \]
    \[
    \resizebox{\linewidth}{!}{$\displaystyle
    VOC_{dr} = \mathrm{PWF} \times D_{wm} \times DC_m \times RD \left[
      \sum_{j=1}^{o} \left\{ (C_{Ti})_j \times (V_{CD})_j \times (CF_T)_j \times (WPI_{Ti})_j \right\}
      + \sum_{k=1}^{p} \left\{ (C_{Di})_k \times (V_{CD})_k \times (CF_D)_k \times (WPI_{Di})_k \right\}
    \right]
    $}
    \]
    \[
    \resizebox{\linewidth}{!}{$\displaystyle
    VOT_{dr} = \mathrm{PWF} \times D_{wm} \times DC_m \times T_{AT} \left[
      \sum_{j=1}^{o} \left\{ (T_{VP})_j \times (V_{CD})_j \times (O_{Avg})_j \times (WPI_{Ti})_j \right\}
      + \sum_{k=1}^{p} \left\{ (CHC_T)_k \times (V_{CD})_k \times (WPI_{Di})_k \right\}
    \right]
    $}
    \]
    \[
    \resizebox{\linewidth}{!}{$\displaystyle
    AC_{dr} = \mathrm{PWF} \times A_{Tn} \left[
      \sum_{j=1}^{o} \left\{ (E_{Vi})_j \times (A_{Di})_j \times (WPI_{me})_j \right\}
      + \sum_{k=1}^{p} \left\{ (E_{VD})_k \times (A_{Ne})_k \times (WPI_{sp})_k \right\}
    \right]
    $}
    \]

  \item \textbf{Road user cost due to rerouting of vehicles during reconstruction}
    \[ \mathrm{RUC}_{re} = \mathrm{VOC}_{re} + \mathrm{VOT}_{re} + \mathrm{AC}_{re} \]
    \[
    \resizebox{\linewidth}{!}{$\displaystyle
    VOC_{re} = \mathrm{PWF} \times D_{wm} \times DC_m \times RD \left[
      \sum_{j=1}^{o} \left\{ (C_{Ti})_j \times (V_{CD})_j \times (CF_T)_j \times (WPI_{Ti})_j \right\}
      + \sum_{k=1}^{p} \left\{ (C_{Di})_k \times (V_{CD})_k \times (CF_D)_k \times (WPI_{Di})_k \right\}
    \right]
    $}
    \]
    (Refer to table B-1 to B-16 to calculate distance and time related costs for VOC)
    \[
    \resizebox{\linewidth}{!}{$\displaystyle
    VOT_{re} = \mathrm{PWF} \times D_{wm} \times DC_m \times T_{AT} \left[
      \sum_{j=1}^{o} \left\{ (T_{VP})_j \times (V_{CD})_j \times (O_{Avg})_j \times (WPI_{Ti})_j \right\}
      + \sum_{k=1}^{p} \left\{ (CHC_T)_k \times (V_{CD})_k \times (WPI_{Di})_k \right\}
    \right]
    $}
    \]
    \[
    \resizebox{\linewidth}{!}{$\displaystyle
    AC_{re} = \mathrm{PWF} \times A_{Tn} \left[
      \sum_{j=1}^{o} \left\{ (E_{Vi})_j \times (A_{Di})_j \times (WPI_{me})_j \right\}
      + \sum_{k=1}^{p} \left\{ (E_{VD})_k \times (A_{Ne})_k \times (WPI_{sp})_k \right\}
    \right]
    $}
    \]

  \item \textbf{Road user cost due to rerouting of vehicles during demolition at the end of life}
    \[ \mathrm{RUC}_{df} = \mathrm{VOC}_{df} + \mathrm{VOT}_{df} + \mathrm{AC}_{df} \]
    \[
    \resizebox{\linewidth}{!}{$\displaystyle
    VOC_{df} = \mathrm{PWF} \times D_{wm} \times DC_m \times RD \left[
      \sum_{j=1}^{o} \left\{ (C_{Ti})_j \times (V_{CD})_j \times (CF_T)_j \times (WPI_{Ti})_j \right\}
      + \sum_{k=1}^{p} \left\{ (C_{Di})_k \times (V_{CD})_k \times (CF_D)_k \times (WPI_{Di})_k \right\}
    \right]
    $}
    \]
    (Refer to table B-1 to B-16 to calculate distance and time related costs for VOC)
    \[
    \resizebox{\linewidth}{!}{$\displaystyle
    VOT_{df} = \mathrm{PWF} \times D_{wm} \times DC_m \times T_{AT} \left[
      \sum_{j=1}^{o} \left\{ (T_{VP})_j \times (V_{CD})_j \times (O_{Avg})_j \times (WPI_{Ti})_j \right\}
      + \sum_{k=1}^{p} \left\{ (CHC_T)_k \times (V_{CD})_k \times (WPI_{Di})_k \right\}
    \right]
    $}
    \]
    \[
    \resizebox{\linewidth}{!}{$\displaystyle
    AC_{df} = \mathrm{PWF} \times A_{Tn} \left[
      \sum_{j=1}^{o} \left\{ (E_{Vi})_j \times (A_{Di})_j \times (WPI_{me})_j \right\}
      + \sum_{k=1}^{p} \left\{ (E_{VD})_k \times (A_{Ne})_k \times (WPI_{sp})_k \right\}
    \right]
    $}
    \]
\end{itemize}

\vspace{0.3em}
\textbf{B.3.3 Environmental cost}
\addcontentsline{toc}{subsubsection}{B.3.3 Environmental cost}

\textbf{Carbon Emission Cost}

\begin{itemize}[leftmargin=*]
  \item Carbon emission cost due to demolition and disposal for reconstruction
    \[ \mathrm{DR}_{\mathrm{EC}} = \mathrm{PWF} \times P_{\mathrm{IECd}} \]

  \item Carbon emission cost due to rerouting of vehicles during demolition for reconstruction
    \begin{align*}
    \mathrm{VEC}_{\mathrm{DR}}
    &= \mathrm{PWF} \times \mathrm{SCC} \times D_{wm} \times \mathrm{DC}_m \times \mathrm{RD} \\
    &\quad \times \sum_{k=1}^{p} (\mathrm{ADT})_k\, (\mathrm{EF}_v)_k
    \end{align*}

  \item Carbon emission cost due to reconstruction
    \[ \mathrm{REC}_{\mathrm{EC}} = \mathrm{PWF} \times \mathrm{IEC} \]

  \item Carbon emission cost due to rerouting of vehicles during reconstruction
    \begin{align*}
    \mathrm{VEC}_{\mathrm{REC}}
    &= \mathrm{PWF} \times \mathrm{SCC} \times D_{wm} \times \mathrm{DC}_m \times \mathrm{RD} \\
    &\quad \times \sum_{k=1}^{p} (\mathrm{ADT})_k\, (\mathrm{EF}_v)_k
    \end{align*}

  \item Carbon emission cost due to demolition and disposal at end of life
    \[ \mathrm{DF}_{\mathrm{EC}} = \mathrm{PWF} \times P_{\mathrm{IECd}} \]

  \item Carbon emission cost due to rerouting of vehicles during demolition at end of life
    \begin{align*}
    \mathrm{VEC}_{\mathrm{DF}}
    &= \mathrm{PWF} \times \mathrm{SCC} \times D_{wm} \times \mathrm{DC}_m \times \mathrm{RD} \\
    &\quad \times \sum_{k=1}^{p} (\mathrm{ADT})_k\, (\mathrm{EF}_v)_k
    \end{align*}
\end{itemize}



    """
