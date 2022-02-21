import {RouterModule, Routes} from "@angular/router";
import {LogsContainer} from "./containers/logs/logs.container";
import {LabContainer} from "./containers/lab/lab.container";
import {EmailContainer} from "./containers/email/email.container";
import {NgModule} from "@angular/core";

const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    redirectTo: '/logs'
  },
  {
    path: 'logs',
    component: LogsContainer
  },
  {
    path: 'labs',
    component: LabContainer
  },
  {
    path: 'emails',
    component: EmailContainer
  },
  {
    path: '**',
    pathMatch: 'full',
    redirectTo: '/logs'
  },
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule {
}
