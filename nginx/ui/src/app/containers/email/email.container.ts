import {Component} from '@angular/core';
import {FormBuilder, FormControl, FormGroup, Validators} from "@angular/forms";
import {catchError, delay} from "rxjs/internal/operators";
import {config, Observable, of, Subject, throwError} from "rxjs";
import {HttpClient} from "@angular/common/http";

@Component({
  selector: 'email-page',
  templateUrl: './email.container.html',
  styleUrls: ['./email.container.css']
})
export class EmailContainer {

  readonly formGroup: FormGroup;
  readonly currentTask$: Subject<string> = new Subject<string>();
  readonly configs$: Observable<string[]>;

  constructor(fb: FormBuilder, readonly http: HttpClient) {

    this.formGroup = fb.group({
      config: ['', Validators.required],
      dry_run: [false, Validators.required],
      logs_vv: [true, Validators.required]
    });

    this.configs$ = this.http.get<string[]>('/api/v1/configs')
      .pipe(
        catchError((error) => {
          alert(error.error);
          return throwError(error);
        })
      );
  }

  startHandler() {

    this.http.post<string>('/api/v1/emails', this.formGroup.value)
      .pipe(
        catchError((error) => {
          alert(error.error);
          return throwError(error);
        })
      )
      .subscribe((id: string) => {
        this.formGroup.disable();
        this.currentTask$.next(id);
      });
  }
}
