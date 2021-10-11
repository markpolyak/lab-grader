import {BrowserModule} from '@angular/platform-browser';
import {NgModule} from '@angular/core';
import {LabContainer} from "./containers/lab/lab.container";
import {EmailContainer} from "./containers/email/email.container";
import {LogsContainer} from "./containers/logs/logs.container";
import {LogViewerComponent} from "./components/log-viewer/log-viewer.component";
import {MainContainer} from "./containers/main/main.container";
import {BrowserAnimationsModule} from '@angular/platform-browser/animations';
import {AppRoutingModule} from "./app.routing";
import {MatToolbarModule} from "@angular/material/toolbar";
import {MatListModule} from "@angular/material/list";
import {MatProgressSpinnerModule} from "@angular/material/progress-spinner";
import {HttpClientModule} from "@angular/common/http";
import {MatCardModule} from "@angular/material/card";
import {MatButtonModule} from "@angular/material/button";
import {MatSelectModule} from "@angular/material/select";
import {ReactiveFormsModule} from "@angular/forms";
import {MatCheckboxModule} from "@angular/material/checkbox";
import {MatInputModule} from "@angular/material/input";

@NgModule({
  declarations: [
    MainContainer,
    LabContainer,
    EmailContainer,
    LogsContainer,
    LogViewerComponent
  ],
    imports: [
        BrowserModule,
        BrowserAnimationsModule,
        HttpClientModule,
        AppRoutingModule,
        MatToolbarModule,
        MatListModule,
        MatProgressSpinnerModule,
        MatCardModule,
        MatButtonModule,
        MatSelectModule,
        ReactiveFormsModule,
        MatCheckboxModule,
        MatInputModule
    ],
  providers: [],
  bootstrap: [MainContainer]
})
export class AppModule {
}
