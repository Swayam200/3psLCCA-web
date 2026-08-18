
from pylatex import NoEscape

APPENDIX_A_LATEX = r"""

\clearpage

\section*{\fontsize{14pt}{16pt}\selectfont\bfseries Summary and Conclusions}
\addcontentsline{toc}{section}{Summary and Conclusions}

\noindent
The LCCA results indicate the relative contribution of construction, road user, and environmental costs, supporting informed and sustainable bridge planning decisions.

\vspace{0.3em}

\noindent
The most contributing stage of the life cycle is \underline{\hspace{3cm}} 
contributing to around \underline{\hspace{2cm}}\% of the total life cycle cost.

\vspace{0.3em}

\noindent
The most contributing pillar is \underline{\hspace{3cm}} contributing to around \underline{\hspace{2cm}}\% of the total life cycle cost.

\vspace{0.5em}

\begin{itemize}
\item User conclusions or remarks.
\end{itemize}

\vspace{0.5em}

\textbf{Note:} The above life cycle cost calculations do not include all components of
the 3PS-LCC framework. Certain cost elements have been excluded from the analysis.
The specific life cycle cost components that were included and excluded in the above
calculations are listed below.

\vspace{0.5em}

\textbf{Life cycle cost components (Included)}

\begin{itemize}
\item Initial construction costs
\item Initial carbon emissions (materials)
\item Initial carbon emissions (on-site)
\item Initial carbon emission (transportation of material)
\item Time costs
\item Road user costs during initial construction
\item Carbon emissions due to rerouting during initial construction (vehicles)
\item Routine inspection costs
\item Periodic maintenance costs
\item Periodic maintenance carbon emissions (materials)
\item Major inspection costs
\item Major repair costs
\item Major repair-related carbon emissions (materials)
\item Road user costs during major repairs
\item Carbon emissions due to rerouting during major repairs (vehicles)
\item Replacement cost of bearings and expansion joints
\item Road user costs during replacement
\item Carbon emissions due to rerouting during replacement (vehicles)
\item Demolition and disposal costs of the existing bridge
\item Demolition and disposal-related carbon emissions (materials) of the existing bridge
\item Road user costs during demolition and disposal of the existing bridge
\item Carbon emissions due to rerouting during demolition and disposal (vehicles) of the existing bridge
\item Recycling costs for reconstruction
\item Reconstruction costs
\item Reconstruction carbon emissions (materials)
\item Reconstruction time costs
\item Road user costs during reconstruction
\item Carbon emissions due to rerouting during reconstruction (vehicles)
\item Final demolition and disposal costs
\item Final demolition and disposal-related carbon emissions (materials)
\item Road user costs during final demolition and disposal
\item Carbon emissions due to rerouting during final demolition and disposal (vehicles)
\item Recycling costs
\end{itemize}
....\\
....\\
....\\

\vspace{0.5em}

\textbf{Life cycle cost components (Excluded)}\\
\vspace{0.5em}
....


\clearpage
\appendix
\pagestyle{empty}

\section*{\fontsize{14pt}{16pt}\selectfont\bfseries Appendix A: Assumptions}
\addcontentsline{toc}{section}{Appendix A: Assumptions}

\noindent
This Life Cycle Cost Assessment (LCCA) has been carried out using a deterministic,
software-based approach. The analysis is based on standard engineering practice,
published guidelines, and reasonable assumptions adopted to ensure consistency,
transparency, and comparability of results. The key assumptions adopted in the
present study are summarized below.

\vspace{0.5em}

\begin{itemize}
\item The analysis period corresponds to the \textbf{design/service life of the bridge} as specified in the project data.
\item The study includes: initial construction, routine inspection, periodic maintenance, major inspections, repairs, replacement of bearings and expansion joints, reconstruction, demolition and disposal, and associated road user costs.
\item Only greenhouse gas (GHG) emissions are considered for environmental cost monetization.
\item Other impacts such as noise pollution, local business impacts, regional economic disruptions, and broader social externalities are outside the scope of this study.
\item Components not explicitly defined in the input data or methodology are excluded.
\item Future technological advancement, policy changes, traffic growth variations, or economic structural shifts are not considered.
\item All costs are converted into present value terms.
\item The discounting approach is based on standard economic theory where future costs and benefits are adjusted to present value using a constant discount rate.
\item Inflation and interest rates are assumed constant over the analysis period.
\item Real interest rate principles are used in deriving the discount relationship.
\item Wholesale Price Index (WPI) ratios are used for escalation of specific cost components based on their respective commodity categories. WPI categories are used for adjusting the following components:
  \begin{itemize}
  \item Passenger and crew cost $\rightarrow$ ``All Commodities''
  \item Property damage and spare parts $\rightarrow$ ``Manufacture of parts and accessories for motor vehicles''
  \item Human injury cost $\rightarrow$ ``Medical accessories''
  \item Petrol $\rightarrow$ ``Mineral Oils''
  \item Diesel $\rightarrow$ ``HSD (High Speed Diesel)''
  \item Engine oil $\rightarrow$ ``Lube oils''
  \item Grease and related oils $\rightarrow$ ``Mineral oil (grouped)''
  \item Tyre costs (by vehicle category) $\rightarrow$ Corresponding tyre index categories
  \item Fixed and depreciation cost $\rightarrow$ ``Manufacture of motor vehicles, trailers and semi-trailers''
  \item Commodity holding cost $\rightarrow$ ``Fuel \& Power''
  \end{itemize}
\item Initial construction costs are based on estimated quantities and prevailing unit rates from SOR.
\item Carbon emissions during construction are calculated using emission factors for material, transportation and energy consumption.
\item Emission factors are assumed constant over the entire analysis period.
\item Transportation of materials occurs under normal traffic and operating conditions.
\item Maintenance and repair emissions are assumed proportional to initial construction emissions.
\item Demolition and disposal emissions are assumed proportional to construction emissions.
\item Recycling is assumed to generate cost recovery (treated as negative cost).
\item Environmental cost is calculated by monetizing carbon emissions using a single Social Cost of Carbon (SCC) value.
\item Average Daily Traffic (ADT) is assumed constant within each defined analysis period.
\item Traffic composition (cars, two-wheelers, buses, LCVs, HCVs, MCVs) is based on input data.
\item Traffic diversion during construction, maintenance, repair, replacement, reconstruction, and demolition is assumed over a predefined detour length.
\item Vehicle operating cost, value of time, and accident cost are calculated using standard equations and accepted parameters.
\item Uniform traffic flow and average operating conditions are assumed during rerouting.
\item Routine inspections, periodic maintenance, major inspections, and repairs occur at fixed predefined intervals.
\item Maintenance and repair costs are calculated as a percentage of initial construction or superstructure cost.
\item Replacement activities are limited to bearings and expansion joints.
\item Reconstruction involves demolition of the existing bridge followed by construction of a new bridge with similar functional characteristics.
\item All interventions occur as scheduled without unplanned delays unless explicitly stated.
\end{itemize}


\clearpage

\appendix
\pagestyle{empty}

\section*{\fontsize{14pt}{16pt}\selectfont\bfseries Appendix A: Assumptions}

\noindent
This Life Cycle Cost Assessment (LCCA) has been carried out using a deterministic,
software-based approach grounded in standard engineering practice, published literature,
and national economic data. The assumptions adopted ensure consistency, transparency,
and comparability of results.

\vspace{0.5em}

\begin{itemize}
\item The analysis period corresponds to the \textbf{design/service life of the bridge} as specified in the project data.
\item The study includes: initial construction, routine inspection, periodic maintenance, major inspections, repairs, replacement of bearings and expansion joints, reconstruction, demolition and disposal, and associated road user costs.
\item Only greenhouse gas (GHG) emissions are considered for environmental cost monetization.
\item Other impacts such as noise pollution, local business impacts, regional economic disruptions, and broader social externalities are outside the scope of this study.
\item Components not explicitly defined in the input data or methodology are excluded.
\item Future technological advancement, policy changes, traffic growth variations, or economic structural shifts are not considered.
\item All costs are converted into present value terms.
\item The discounting approach is based on standard economic theory where future costs and benefits are adjusted to present value using a constant discount rate.
\item Inflation and interest rates are assumed constant over the analysis period.
\item Real interest rate principles are used in deriving the discount relationship.
\item Wholesale Price Index (WPI) ratios are used for escalation of specific cost components based on their respective commodity categories. WPI categories are used for adjusting the following components:
  \begin{itemize}
  \item Passenger and crew cost $\rightarrow$ ``All Commodities''
  \item Property damage and spare parts $\rightarrow$ ``Manufacture of parts and accessories for motor vehicles''
  \item Human injury cost $\rightarrow$ ``Medical accessories''
  \item Petrol $\rightarrow$ ``Mineral Oils''
  \item Diesel $\rightarrow$ ``HSD (High Speed Diesel)''
  \item Engine oil $\rightarrow$ ``Lube oils''
  \item Grease and related oils $\rightarrow$ ``Mineral oil (grouped)''
  \item Tyre costs (by vehicle category) $\rightarrow$ Corresponding tyre index categories
  \item Fixed and depreciation cost $\rightarrow$ ``Manufacture of motor vehicles, trailers and semi-trailers''
  \item Commodity holding cost $\rightarrow$ ``Fuel \& Power''
  \end{itemize}
\item Initial construction costs are based on estimated quantities and prevailing unit rates from SOR.
\item Carbon emissions during construction are calculated using emission factors for material, transportation and energy consumption.
\item Emission factors are assumed constant over the entire analysis period.
\item Transportation of materials occurs under normal traffic and operating conditions.
\item Maintenance and repair emissions are assumed proportional to initial construction emissions.
\item Demolition and disposal emissions are assumed proportional to construction emissions.
\item Recycling is assumed to generate cost recovery (treated as negative cost).
\item Environmental cost is calculated by monetizing carbon emissions using a single Social Cost of Carbon (SCC) value.
\item Average Daily Traffic (ADT) is assumed constant within each defined analysis period.
\item Traffic composition (cars, two-wheelers, buses, LCVs, HCVs, MCVs) is based on input data.
\item Traffic diversion during construction, maintenance, repair, replacement, reconstruction, and demolition is assumed over a predefined detour length.
\item Vehicle operating cost, value of time, and accident cost are calculated using standard equations and accepted parameters.
\item Uniform traffic flow and average operating conditions are assumed during rerouting.
\item Routine inspections, periodic maintenance, major inspections, and repairs occur at fixed predefined intervals.
\item Maintenance and repair costs are calculated as a percentage of initial construction or superstructure cost.
\item Replacement activities are limited to bearings and expansion joints.
\item Reconstruction involves demolition of the existing bridge followed by construction of a new bridge with similar functional characteristics.
\item All interventions occur as scheduled without unplanned delays unless explicitly stated.
\end{itemize}
"""